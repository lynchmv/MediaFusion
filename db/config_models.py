"""
Domain-specific configuration models for MediaFusion.
Split from the monolithic Settings class for better organization and maintainability.
"""
from typing import Literal

from pydantic import Field, BaseModel


class CoreConfig(BaseModel):
    """Core application configuration."""
    addon_name: str = "MediaFusion"
    version: str = "1.0.0"
    description: str = (
        "Universal Stremio Add-on for Movies, Series, Live TV & Sports Events. "
        "Source: https://github.com/mhdzumair/MediaFusion"
    )
    branding_description: str = ""
    contact_email: str = "mhdzumair@gmail.com"
    host_url: str
    secret_key: str = Field(..., max_length=32, min_length=32)
    api_password: str
    logo_url: str = (
        "https://raw.githubusercontent.com/mhdzumair/MediaFusion/main/resources/images/mediafusion_logo.png"
    )
    is_public_instance: bool = False
    poster_host_url: str | None = None
    min_scraping_video_size: int = 26214400  # 25 MB in bytes
    metadata_primary_source: Literal["imdb", "tmdb"] = "imdb"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    logging_level: str = "INFO"
    logging_format: Literal["structured", "json"] = "structured"


class DatabaseConfig(BaseModel):
    """Database and cache configuration."""
    mongo_uri: str
    postgres_uri: str  # Primary read-write PostgreSQL URI
    postgres_read_uri: str | None = None  # Optional read replica URI
    db_max_connections: int = 50
    redis_url: str = "redis://redis-service:6379"
    redis_max_connections: int = 100
    redis_retry_attempts: int = 3
    redis_retry_delay: float = 0.1
    redis_connection_timeout: int = 10
    redis_enable_circuit_breaker: bool = True


class ExternalServiceConfig(BaseModel):
    """External service URLs and API keys."""
    requests_proxy_url: str | None = None
    playwright_cdp_url: str = "ws://browserless:3000?blockAds=true&stealth=true"
    flaresolverr_url: str = "http://flaresolverr:8191/v1"
    tmdb_api_key: str | None = None
    premiumize_oauth_client_id: str | None = None
    premiumize_oauth_client_secret: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class StreamingProviderConfig(BaseModel):
    """Streaming provider configuration."""
    disabled_providers: list[
        Literal[
            "p2p",
            "realdebrid",
            "seedr",
            "debridlink",
            "alldebrid",
            "offcloud",
            "pikpak",
            "torbox",
            "premiumize",
            "qbittorrent",
            "stremthru",
            "easydebrid",
            "debrider",
        ]
    ] = Field(default_factory=list)


class ProwlarrConfig(BaseModel):
    """Prowlarr scraper configuration."""
    is_scrap_from_prowlarr: bool = True
    prowlarr_url: str = "http://prowlarr-service:9696"
    prowlarr_api_key: str | None = None
    prowlarr_live_title_search: bool = True
    prowlarr_background_title_search: bool = True
    prowlarr_search_query_timeout: int = 30
    prowlarr_search_interval_hour: int = 72
    prowlarr_immediate_max_process: int = 10
    prowlarr_immediate_max_process_time: int = 15
    prowlarr_feed_scrape_interval_hour: int = 3


class JackettConfig(BaseModel):
    """Jackett scraper configuration."""
    is_scrap_from_jackett: bool = False
    jackett_url: str = "http://jackett-service:9117"
    jackett_api_key: str | None = None
    jackett_search_interval_hour: int = 72
    jackett_search_query_timeout: int = 30
    jackett_immediate_max_process: int = 10
    jackett_immediate_max_process_time: int = 15
    jackett_live_title_search: bool = True
    jackett_background_title_search: bool = True
    jackett_feed_scrape_interval_hour: int = 3


class BT4GConfig(BaseModel):
    """BT4G scraper configuration."""
    is_scrap_from_bt4g: bool = True
    bt4g_url: str = "https://bt4gprx.com"
    bt4g_search_interval_hour: int = 72
    bt4g_search_timeout: int = 10
    bt4g_immediate_max_process: int = 15
    bt4g_immediate_max_process_time: int = 15


class TorrentioConfig(BaseModel):
    """Torrentio scraper configuration."""
    is_scrap_from_torrentio: bool = False
    torrentio_search_interval_days: int = 3
    torrentio_url: str = "https://torrentio.strem.fun"


class MediaFusionConfig(BaseModel):
    """MediaFusion scraper configuration."""
    is_scrap_from_mediafusion: bool = False
    mediafusion_search_interval_days: int = 3
    mediafusion_url: str = "https://mediafusion.elfhosted.com"
    mediafusion_api_password: str | None = None
    sync_debrid_cache_streams: bool = False
    rss_feed_scrape_interval_hour: int = 3


class ZileanConfig(BaseModel):
    """Zilean scraper configuration."""
    is_scrap_from_zilean: bool = False
    zilean_search_interval_hour: int = 24
    zilean_url: str = "https://zilean.elfhosted.com"


class ScraperConfig(BaseModel):
    """Aggregated scraper configuration."""
    prowlarr: ProwlarrConfig = Field(default_factory=ProwlarrConfig)
    jackett: JackettConfig = Field(default_factory=JackettConfig)
    bt4g: BT4GConfig = Field(default_factory=BT4GConfig)
    torrentio: TorrentioConfig = Field(default_factory=TorrentioConfig)
    mediafusion: MediaFusionConfig = Field(default_factory=MediaFusionConfig)
    zilean: ZileanConfig = Field(default_factory=ZileanConfig)
    is_scrap_from_yts: bool = True
    scrape_with_aka_titles: bool = True
    enable_fetching_torrent_metadata_from_p2p: bool = True
    background_search_interval_hours: int = 72
    background_search_crontab: str = "*/3 * * * *"


class SchedulerConfig(BaseModel):
    """Scheduler configuration."""
    disable_all_scheduler: bool = False
    
    # Individual scheduler crontabs
    tamilmv_scheduler_crontab: str = "0 */3 * * *"
    disable_tamilmv_scheduler: bool = False
    tamil_blasters_scheduler_crontab: str = "0 */6 * * *"
    disable_tamil_blasters_scheduler: bool = False
    formula_tgx_scheduler_crontab: str = "*/30 * * * *"
    disable_formula_tgx_scheduler: bool = True
    nowmetv_scheduler_crontab: str = "0 0 * * 5"
    disable_nowmetv_scheduler: bool = True
    nowsports_scheduler_crontab: str = "0 10 * * 5"
    disable_nowsports_scheduler: bool = True
    tamilultra_scheduler_crontab: str = "0 8 * * 5"
    disable_tamilultra_scheduler: bool = False
    validate_tv_streams_in_db_crontab: str = "0 0 * * 4"
    disable_validate_tv_streams_in_db: bool = False
    sport_video_scheduler_crontab: str = "*/20 * * * *"
    disable_sport_video_scheduler: bool = False
    dlhd_scheduler_crontab: str = "0 0 * * 1"
    disable_dlhd_scheduler: bool = False
    motogp_tgx_scheduler_crontab: str = "0 5 * * *"
    disable_motogp_tgx_scheduler: bool = True
    update_seeders_crontab: str = "0 0 * * 3"
    disable_update_seeders: bool = True
    arab_torrents_scheduler_crontab: str = "0 0 * * *"
    disable_arab_torrents_scheduler: bool = False
    wwe_tgx_scheduler_crontab: str = "10 */3 * * *"
    disable_wwe_tgx_scheduler: bool = True
    ufc_tgx_scheduler_crontab: str = "30 */3 * * *"
    disable_ufc_tgx_scheduler: bool = True
    movies_tv_tgx_scheduler_crontab: str = "0 * * * *"
    disable_movies_tv_tgx_scheduler: bool = True
    prowlarr_feed_scraper_crontab: str = "0 */3 * * *"
    disable_prowlarr_feed_scraper: bool = False
    jackett_feed_scraper_crontab: str = "0 */3 * * *"
    disable_jackett_feed_scraper: bool = False
    rss_feed_scraper_crontab: str = "0 */3 * * *"
    disable_rss_feed_scraper: bool = False
    cleanup_expired_scraper_task_crontab: str = "0 * * * *"
    cleanup_expired_cache_task_crontab: str = "0 0 * * *"


class FeatureConfig(BaseModel):
    """Feature toggles and content filtering."""
    enable_rate_limit: bool = True
    validate_m3u8_urls_liveness: bool = True
    store_stremthru_magnet_cache: bool = False
    adult_content_regex_keywords: str = (
        r"(^|\b|\s|$|[\[._-])"
        r"(18\s*\+|adults?|porn|sex|xxx|nude|boobs?|pussy|ass|bigass|bigtits?|blowjob|hardfuck|onlyfans?|naked|hot|milf|slut|doggy|anal|threesome|foursome|erotic|sexy|18\s*plus|trailer|RiffTrax|zipx)"
        r"(\b|\s|$|[\]._-])"
    )
    adult_content_filter_in_torrent_title: bool = True
    meta_cache_ttl: int = 1800  # 30 minutes in seconds
    worker_max_tasks_per_child: int = 20


class ConfigSourceConfig(BaseModel):
    """Configuration source settings."""
    use_config_source: str = "remote"
    remote_config_source: str = (
        "https://raw.githubusercontent.com/mhdzumair/MediaFusion/main/resources/json/scraper_config.json"
    )
    local_config_path: str = "resources/json/scraper_config.json"
