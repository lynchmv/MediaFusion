"""
Cache management utilities for MediaFusion.
Provides helpers for cache invalidation and management.
"""
import logging
from typing import List, Optional

from db.redis_database import REDIS_ASYNC_CLIENT

logger = logging.getLogger(__name__)


async def invalidate_metadata_cache(media_id: str, media_type: str = "movie") -> None:
    """
    Invalidate metadata cache for a specific media item.
    
    Args:
        media_id: Media identifier
        media_type: Type of media (movie, series, tv)
    """
    cache_keys = [
        f"{media_type}_exists:{media_id}",
        f"{media_type}:{media_id}",
        f"catalog:*:{media_id}",
    ]
    
    # Delete specific keys
    for key in cache_keys[:2]:  # Only delete exact keys, not patterns
        try:
            await REDIS_ASYNC_CLIENT.delete(key)
        except Exception as e:
            logger.warning(f"Failed to delete cache key {key}: {e}")


async def invalidate_catalog_cache(
    catalog_type: str,
    catalog_id: Optional[str] = None,
    genre: Optional[str] = None,
) -> None:
    """
    Invalidate catalog cache entries.
    
    Args:
        catalog_type: Type of catalog (movie, series, tv)
        catalog_id: Optional specific catalog ID to invalidate
        genre: Optional genre filter to invalidate
    """
    # Note: Pattern-based deletion requires SCAN which is expensive
    # For now, we'll let cache expire naturally or invalidate on updates
    logger.debug(f"Catalog cache invalidation requested for {catalog_type}/{catalog_id}")


async def invalidate_stream_cache(video_id: str, season: Optional[int] = None, episode: Optional[int] = None) -> None:
    """
    Invalidate cached stream data for a video.
    
    Args:
        video_id: Video metadata ID
        season: Optional season number
        episode: Optional episode number
    """
    cache_key_parts = ["torrent_streams", video_id]
    if season is not None and episode is not None:
        cache_key_parts.extend([str(season), str(episode)])
    cache_key = ":".join(cache_key_parts)
    
    try:
        await REDIS_ASYNC_CLIENT.delete(cache_key)
    except Exception as e:
        logger.warning(f"Failed to delete stream cache key {cache_key}: {e}")


async def bulk_invalidate_cache(keys: List[str]) -> int:
    """
    Bulk invalidate multiple cache keys using Redis pipeline.
    
    Uses Redis pipeline for efficient bulk deletion when possible.
    Falls back to parallel deletion for very large batches.
    
    Args:
        keys: List of cache keys to delete
        
    Returns:
        Number of keys successfully deleted
    """
    if not keys:
        return 0
    
    # Use pipeline for batches up to 1000 keys (Redis pipeline limit)
    if len(keys) <= 1000:
        try:
            async with REDIS_ASYNC_CLIENT.pipeline() as pipe:
                for key in keys:
                    pipe.delete(key)
                results = await pipe.execute()
                # Count successful deletions (1 = deleted, 0 = not found)
                deleted = sum(1 for r in results if r)
                return deleted
        except Exception as e:
            logger.warning(f"Pipeline deletion failed, falling back to parallel: {e}")
    
    # Fallback to parallel deletion for large batches or on error
    import asyncio
    
    # Delete keys in parallel batches of 100
    batch_size = 100
    deleted = 0
    
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        results = await asyncio.gather(*[
            REDIS_ASYNC_CLIENT.delete(key) for key in batch
        ], return_exceptions=True)
        
        # Count successful deletions
        deleted += sum(1 for r in results if r and not isinstance(r, Exception))
    
    if deleted < len(keys):
        failed = len(keys) - deleted
        logger.warning(f"Failed to delete {failed} out of {len(keys)} cache keys")
    
    return deleted
