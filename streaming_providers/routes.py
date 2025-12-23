import logging
from os import path
from os.path import basename
from typing import Annotated, Optional

from fastapi import (
    Request,
    Response,
    HTTPException,
    APIRouter,
    Depends,
    BackgroundTasks,
)
from fastapi.responses import RedirectResponse

from db import schemas, sql_crud
from db.config import settings
from db.database import get_read_session
from db.schemas import (
    CacheStatusResponse,
    CacheStatusRequest,
    StreamingProvider,
    CacheSubmitResponse,
    CacheSubmitRequest,
    TorrentStreamData,
)
from streaming_providers import mapper
from streaming_providers.cache_helpers import (
    store_cached_info_hashes,
    get_cached_status,
)
from streaming_providers.debridlink.api import router as debridlink_router
from streaming_providers.exceptions import ProviderException
from streaming_providers.premiumize.api import router as premiumize_router
from streaming_providers.realdebrid.api import router as realdebrid_router
from streaming_providers.seedr.api import router as seedr_router
from utils import crypto, torrent, wrappers, const
from utils.const import CONTENT_TYPE_HEADERS_MAPPING
from utils.lock import acquire_redis_lock, release_redis_lock
from utils.network import get_user_public_ip, get_user_data, encode_mediaflow_proxy_url
from db.redis_database import REDIS_ASYNC_CLIENT

# Seconds until when the Video URLs are cached
URL_CACHE_EXP = 3600

router = APIRouter()


def generate_cache_key(
    user_ip: str,
    secret_str: str,
    info_hash: str,
    season: Optional[int],
    episode: Optional[int],
) -> str:
    """
    Generate a cache key for streaming provider URLs.
    
    Args:
        user_ip: User's public IP address
        secret_str: User's secret string (encrypted config)
        info_hash: Torrent info hash
        season: Optional season number
        episode: Optional episode number
        
    Returns:
        Cache key string (hashed for security)
    """
    return "streaming_provider_" + crypto.get_text_hash(
        f"{user_ip}_{secret_str}_{info_hash}_{season}_{episode}", full_hash=True
    )


async def get_cached_stream_url_and_redirect(
    cached_stream_url_key: str,
    user_data: schemas.UserData,
    response: Response,
) -> Optional[RedirectResponse]:
    """
    Check for cached stream URL and return a RedirectResponse if available.
    
    Handles MediaFlow proxy encoding if configured.
    
    Args:
        cached_stream_url_key: Redis cache key for the stream URL
        user_data: User configuration data
        response: FastAPI response object
        
    Returns:
        RedirectResponse if cached URL exists, None otherwise
    """
    if cached_stream_url := await get_cached_stream_url(cached_stream_url_key):
        if (
            user_data.mediaflow_config
            and user_data.mediaflow_config.proxy_debrid_streams
        ):
            response_headers = {
                "content-disposition": "attachment, filename={}".format(
                    path.basename(cached_stream_url)
                )
            }
            file_extension = path.splitext(cached_stream_url)[-1]
            content_type = CONTENT_TYPE_HEADERS_MAPPING.get(file_extension)
            if content_type:
                response_headers["Content-Type"] = content_type

            cached_stream_url = encode_mediaflow_proxy_url(
                user_data.mediaflow_config.proxy_url,
                "/proxy/stream",
                cached_stream_url,
                query_params={"api_password": user_data.mediaflow_config.api_password},
                response_headers=response_headers,
            )
        return RedirectResponse(
            url=cached_stream_url, headers=response.headers, status_code=302
        )
    return None


async def fetch_stream_or_404(info_hash: str) -> TorrentStreamData:
    """
    Fetch stream by info hash, raise 404 error if not found.
    
    Returns TorrentStreamData (Pydantic model) to avoid lazy loading issues
    when used outside database session context.
    
    Args:
        info_hash: Torrent info hash
        
    Returns:
        TorrentStreamData: Stream data as Pydantic model
        
    Raises:
        HTTPException: 404 if stream not found
    """    
    async for session in get_read_session():
        stream = await sql_crud.get_stream_by_info_hash(session, info_hash, load_relations=True)
        if stream:
            # Convert to Pydantic model to detach from session
            return TorrentStreamData.from_pg_model(stream)

    raise HTTPException(status_code=400, detail="Stream not found.")


async def get_or_create_video_url(
    stream: TorrentStreamData,
    user_data: schemas.UserData,
    info_hash: str,
    season: Optional[int],
    episode: Optional[int],
    filename: Optional[str],
    user_ip: Optional[str],
    background_tasks: BackgroundTasks,
) -> str:
    """
    Retrieve or generate video URL from streaming provider.
    
    Converts info hash to magnet link, determines file index, and calls
    provider-specific URL generation function.
    
    Args:
        stream: TorrentStreamData with stream information
        user_data: User configuration with streaming provider settings
        info_hash: Torrent info hash
        season: Optional season number for series
        episode: Optional episode number for series
        filename: Optional specific filename to use
        user_ip: Optional user IP address
        background_tasks: Background tasks for async operations
        
    Returns:
        Video URL string from streaming provider
        
    Raises:
        ProviderException: If provider-specific error occurs
    """
    # stream is now TorrentStreamData (Pydantic model) with announce_list
    magnet_link = torrent.convert_info_hash_to_magnet(info_hash, stream.announce_list or [])
    episodes = stream.get_episodes(season, episode)
    if not filename:
        episode_data = episodes[0] if episodes else None
        filename = episode_data.filename if episode_data else stream.filename
        filename = basename(filename) if filename else None
    else:
        episode_data = next(
            (episode for episode in episodes if episode.filename == filename), None
        )
    file_index = episode_data.file_index if episode_data else stream.file_index

    get_video_url = mapper.GET_VIDEO_URL_FUNCTIONS.get(
        user_data.streaming_provider.service
    )
    kwargs = dict(
        info_hash=info_hash,
        magnet_link=magnet_link,
        user_data=user_data,
        filename=filename,
        file_index=file_index,
        user_ip=user_ip,
        season=season,
        episode=episode,
        max_retries=1,
        retry_interval=0,
        stream=stream,
        torrent_name=stream.torrent_name,
        background_tasks=background_tasks,
    )

    return await get_video_url(**kwargs)


async def cache_stream_url(cached_stream_url_key: str, video_url: str) -> None:
    """
    Cache streaming URL in Redis for future use.
    
    Stores URL with expiration time to reduce provider API calls.
    
    Args:
        cached_stream_url_key: Redis cache key
        video_url: Video URL to cache
    """
    await REDIS_ASYNC_CLIENT.set(
        cached_stream_url_key, video_url.encode("utf-8"), ex=URL_CACHE_EXP
    )


def apply_mediaflow_proxy_if_needed(video_url: str, user_data: schemas.UserData) -> str:
    """
    Apply MediaFlow proxy to video URL if user configuration requires it.
    
    Encodes URL with proxy parameters and response headers for streaming.
    
    Args:
        video_url: Original video URL
        user_data: User configuration with MediaFlow settings
        
    Returns:
        Proxied URL if MediaFlow proxy is enabled, original URL otherwise
    """
    if user_data.mediaflow_config and user_data.mediaflow_config.proxy_debrid_streams:
        response_headers = {
            "content-disposition": "attachment, filename={}".format(
                path.basename(video_url)
            )
        }
        file_extension = path.splitext(video_url)[-1]
        content_type = CONTENT_TYPE_HEADERS_MAPPING.get(file_extension)
        if content_type:
            response_headers["Content-Type"] = content_type

        return encode_mediaflow_proxy_url(
            user_data.mediaflow_config.proxy_url,
            "/proxy/stream",
            video_url,
            query_params={"api_password": user_data.mediaflow_config.api_password},
            response_headers=response_headers,
        )
    return video_url


def handle_provider_exception(error: ProviderException, usage: str) -> str:
    """
    Handle provider-specific exceptions and log them.
    
    Logs error details and returns exception video URL for user display.
    
    Args:
        error: ProviderException with error details
        usage: Context string describing where error occurred
        
    Returns:
        URL to exception video file
    """
    logging.error(
        "Provider exception occurred for %s: %s",
        usage,
        error.message,
        exc_info=error.video_file_name == "api_error.mp4",
    )
    return f"{settings.host_url}/static/exceptions/{error.video_file_name}"


def handle_generic_exception(exception: Exception, info_hash: str) -> str:
    """
    Handle generic exceptions and log them.
    
    Logs full exception traceback and returns generic error video URL.
    
    Args:
        exception: Generic exception that occurred
        info_hash: Torrent info hash for context
        
    Returns:
        URL to generic API error video file
    """
    logging.error(
        "Generic exception occurred for %s: %s", info_hash, exception, exc_info=True
    )
    return f"{settings.host_url}/static/exceptions/api_error.mp4"


async def get_cached_stream_url(cached_stream_url_key: str) -> Optional[str]:
    """
    Get cached stream URL from Redis.
    
    Retrieves and decodes cached URL if available and not expired.
    
    Args:
        cached_stream_url_key: Redis cache key
        
    Returns:
        Cached stream URL if found, None otherwise
    """
    if cached_stream_url := await REDIS_ASYNC_CLIENT.getex(
        cached_stream_url_key, ex=URL_CACHE_EXP
    ):
        cached_stream_url = cached_stream_url.decode("utf-8")
        return cached_stream_url
    return None


@router.head("/{secret_str}/playback/{info_hash}", tags=["streaming_provider"])
@router.get("/{secret_str}/playback/{info_hash}", tags=["streaming_provider"])
@router.head(
    "/{secret_str}/playback/{info_hash}/{filename}", tags=["streaming_provider"]
)
@router.get(
    "/{secret_str}/playback/{info_hash}/{filename}", tags=["streaming_provider"]
)
@router.head(
    "/{secret_str}/playback/{info_hash}/{season}/{episode}", tags=["streaming_provider"]
)
@router.get(
    "/{secret_str}/playback/{info_hash}/{season}/{episode}", tags=["streaming_provider"]
)
@router.head(
    "/{secret_str}/playback/{info_hash}/{season}/{episode}/{filename}",
    tags=["streaming_provider"],
)
@router.get(
    "/{secret_str}/playback/{info_hash}/{season}/{episode}/{filename}",
    tags=["streaming_provider"],
)
@wrappers.exclude_rate_limit
@wrappers.auth_required
async def streaming_provider_endpoint(
    secret_str: str,
    info_hash: str,
    response: Response,
    request: Request,
    user_data: Annotated[schemas.UserData, Depends(get_user_data)],
    background_tasks: BackgroundTasks,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    filename: Optional[str] = None,
) -> RedirectResponse:
    """
    Handle streaming provider playback requests.
    
    Main endpoint for streaming provider video playback. Uses caching for performance
    and Redis locking to prevent duplicate download tasks. Supports both movies and
    series with optional filename selection.
    
    Args:
        secret_str: User's secret string (encrypted config)
        info_hash: Torrent info hash
        response: FastAPI response object
        request: FastAPI request object
        user_data: User configuration (injected via dependency)
        background_tasks: Background tasks for async operations
        season: Optional season number for series
        episode: Optional episode number for series
        filename: Optional specific filename to stream
        
    Returns:
        RedirectResponse to video URL or exception video
        
    Raises:
        HTTPException: 400 if no streaming provider configured
        HTTPException: 429 if too many concurrent requests
    """
    response.headers.update(const.NO_CACHE_HEADERS)
    info_hash = info_hash.lower()

    if not user_data.streaming_provider:
        raise HTTPException(status_code=400, detail="No streaming provider set.")

    user_ip = await get_user_public_ip(request, user_data)
    cached_stream_url_key = generate_cache_key(
        user_ip, secret_str, info_hash, season, episode
    )

    # Check for cached stream URL
    cached_stream_url = await get_cached_stream_url_and_redirect(
        cached_stream_url_key, user_data, response
    )
    if cached_stream_url:
        return cached_stream_url

    # Fetch stream from DB
    stream = await fetch_stream_or_404(info_hash)

    # Acquire Redis lock to prevent duplicate download tasks
    acquired, lock = await acquire_redis_lock(
        f"{cached_stream_url_key}_locked", timeout=60, block=True
    )
    if not acquired:
        raise HTTPException(status_code=429, detail="Too many requests.")

    redirect_status_code = 307

    try:
        video_url = await get_or_create_video_url(
            stream,
            user_data,
            info_hash,
            season,
            episode,
            filename,
            user_ip,
            background_tasks,
        )
        await store_cached_info_hashes(user_data.streaming_provider, [info_hash])
        await cache_stream_url(cached_stream_url_key, video_url)
        video_url = apply_mediaflow_proxy_if_needed(video_url, user_data)
        redirect_status_code = 302
    except ProviderException as error:
        video_url = handle_provider_exception(error, info_hash)
    except Exception as e:
        video_url = handle_generic_exception(e, info_hash)
    finally:
        await release_redis_lock(lock)

    return RedirectResponse(
        url=video_url, headers=response.headers, status_code=redirect_status_code
    )


@router.get("/{secret_str}/delete_all_watchlist", tags=["streaming_provider"])
@wrappers.exclude_rate_limit
@wrappers.auth_required
async def delete_all_watchlist(
    request: Request,
    response: Response,
    user_data: schemas.UserData = Depends(get_user_data),
):
    """
    Deletes the entire watchlist for the given user, based on the streaming provider.
    """
    response.headers.update(const.NO_CACHE_HEADERS)

    if not user_data.streaming_provider:
        raise HTTPException(status_code=400, detail="No streaming provider set.")

    user_ip = await get_user_public_ip(request, user_data)
    kwargs = dict(user_data=user_data, user_ip=user_ip)

    # Get the delete watchlist function for the user's streaming provider
    delete_all_watchlist_function = mapper.DELETE_ALL_WATCHLIST_FUNCTIONS.get(
        user_data.streaming_provider.service
    )

    if not delete_all_watchlist_function:
        raise HTTPException(
            status_code=400, detail="Provider does not support this action."
        )

    try:
        await delete_all_watchlist_function(**kwargs)
        video_url = f"{settings.host_url}/static/exceptions/watchlist_deleted.mp4"

    except ProviderException as error:
        # Handle provider-specific exceptions
        video_url = handle_provider_exception(error, "delete_watchlist")

    except Exception as e:
        # Handle generic exceptions
        video_url = handle_generic_exception(e, "delete_watchlist")

    return RedirectResponse(url=video_url, headers=response.headers)


@router.post("/cache/status", response_model=CacheStatusResponse)
@wrappers.exclude_rate_limit
async def check_cache_status(request: CacheStatusRequest):
    """
    Check cache status for multiple info hashes.

    Args:
        request: CacheStatusRequest containing service name and list of info hashes

    Returns:
        Dictionary mapping info hashes to their cache status
    """
    if not request.info_hashes:
        return CacheStatusResponse(cached_status={})

    # Create streaming provider object
    provider = StreamingProvider(service=request.service, token="")

    try:
        # Get cache status using existing helper
        cached_status = await get_cached_status(provider, request.info_hashes)
        return CacheStatusResponse(cached_status=cached_status)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking cache status: {str(e)}"
        )


@router.post("/cache/submit", response_model=CacheSubmitResponse)
@wrappers.exclude_rate_limit
async def submit_cached_hashes(request: CacheSubmitRequest):
    """
    Submit cached info hashes to the central cache.

    Args:
        request: CacheSubmitRequest containing service name and list of cached info hashes

    Returns:
        Success status and message
    """
    if not request.info_hashes:
        return CacheSubmitResponse(success=True, message="No info hashes provided")

    provider = StreamingProvider(service=request.service, token="")
    try:
        # Store cache info using existing helper
        await store_cached_info_hashes(provider, request.info_hashes)
        return CacheSubmitResponse(
            success=True,
            message=f"Successfully stored {len(request.info_hashes)} cached info hashes",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error storing cached info hashes: {str(e)}"
        )


router.include_router(seedr_router, prefix="/seedr", tags=["seedr"])
router.include_router(realdebrid_router, prefix="/realdebrid", tags=["realdebrid"])
router.include_router(debridlink_router, prefix="/debridlink", tags=["debridlink"])
router.include_router(premiumize_router, prefix="/premiumize", tags=["premiumize"])
