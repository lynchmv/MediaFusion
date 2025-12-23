"""
Business metrics for MediaFusion operations.
Tracks cache performance, scraper success rates, and API performance.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from prometheus_client import Counter, Histogram, Gauge
from db.redis_database import REDIS_ASYNC_CLIENT

logger = logging.getLogger(__name__)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    labelnames=["cache_type", "operation"]
)
cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    labelnames=["cache_type", "operation"]
)
cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    labelnames=["cache_type", "operation", "status"]
)

# Scraper metrics
scraper_runs_total = Counter(
    "scraper_runs_total",
    "Total number of scraper runs",
    labelnames=["scraper_name", "status"]
)
scraper_items_processed = Counter(
    "scraper_items_processed_total",
    "Total number of items processed by scrapers",
    labelnames=["scraper_name", "status"]
)
scraper_duration_seconds = Histogram(
    "scraper_duration_seconds",
    "Time spent running scrapers",
    labelnames=["scraper_name"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

# API metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    labelnames=["endpoint", "method", "status_code"]
)
api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "Time spent processing API requests",
    labelnames=["endpoint", "method"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10]
)

# Database metrics
database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Time spent executing database queries",
    labelnames=["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2]
)
database_connections_active = Gauge(
    "database_connections_active",
    "Number of active database connections",
    labelnames=["database_type"]
)

# Streaming provider metrics
streaming_provider_requests_total = Counter(
    "streaming_provider_requests_total",
    "Total number of streaming provider API requests",
    labelnames=["provider", "operation", "status"]
)
streaming_provider_duration_seconds = Histogram(
    "streaming_provider_duration_seconds",
    "Time spent on streaming provider operations",
    labelnames=["provider", "operation"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)


def record_cache_hit(cache_type: str, operation: str) -> None:
    """Record a cache hit."""
    cache_hits_total.labels(cache_type=cache_type, operation=operation).inc()
    cache_operations_total.labels(
        cache_type=cache_type, operation=operation, status="hit"
    ).inc()


def record_cache_miss(cache_type: str, operation: str) -> None:
    """Record a cache miss."""
    cache_misses_total.labels(cache_type=cache_type, operation=operation).inc()
    cache_operations_total.labels(
        cache_type=cache_type, operation=operation, status="miss"
    ).inc()


def record_scraper_run(scraper_name: str, status: str, items_processed: int = 0) -> None:
    """Record a scraper run."""
    scraper_runs_total.labels(scraper_name=scraper_name, status=status).inc()
    if items_processed > 0:
        scraper_items_processed.labels(
            scraper_name=scraper_name, status=status
        ).inc(items_processed)


def record_api_request(endpoint: str, method: str, status_code: int, duration: float) -> None:
    """Record an API request."""
    api_requests_total.labels(
        endpoint=endpoint, method=method, status_code=str(status_code)
    ).inc()
    api_request_duration_seconds.labels(endpoint=endpoint, method=method).observe(duration)


def record_database_query(operation: str, table: str, duration: float) -> None:
    """Record a database query."""
    database_query_duration_seconds.labels(operation=operation, table=table).observe(duration)


def record_streaming_provider_request(
    provider: str, operation: str, status: str, duration: float
) -> None:
    """Record a streaming provider request."""
    streaming_provider_requests_total.labels(
        provider=provider, operation=operation, status=status
    ).inc()
    streaming_provider_duration_seconds.labels(
        provider=provider, operation=operation
    ).observe(duration)


async def get_cache_statistics() -> Dict[str, Any]:
    """
    Get cache statistics including hit/miss ratios.
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        # Get cache metrics from Prometheus
        # Note: This is a simplified version - in production you'd query Prometheus
        # or maintain these stats in Redis
        
        # Calculate hit ratio from counters (simplified - would need Prometheus query in production)
        return {
            "cache_types": ["metadata", "torrent_streams", "genres", "catalogs"],
            "note": "Detailed cache statistics available via Prometheus metrics endpoint",
        }
    except Exception as e:
        logger.error(f"Error getting cache statistics: {e}")
        return {"error": str(e)}


async def get_scraper_statistics() -> Dict[str, Any]:
    """
    Get scraper statistics including success rates.
    
    Returns:
        Dictionary with scraper statistics
    """
    try:
        # Get scraper metrics from Redis
        scraper_stats = {}
        
        # Get last run times for all scrapers
        spider_names = [
            "tamilmv", "tamil_blasters", "formula_tgx", "sport_video",
            "dlhd", "motogp_tgx", "arab_torrents", "wwe_tgx", "ufc_tgx"
        ]
        
        for spider_name in spider_names:
            last_run_key = f"background_tasks:run_spider:spider_name={spider_name}"
            last_run = await REDIS_ASYNC_CLIENT.get(last_run_key)
            if last_run:
                scraper_stats[spider_name] = {
                    "last_run": float(last_run),
                    "last_run_readable": datetime.fromtimestamp(float(last_run)).isoformat(),
                }
        
        return {
            "scrapers": scraper_stats,
            "note": "Detailed scraper statistics available via Prometheus metrics endpoint",
        }
    except Exception as e:
        logger.error(f"Error getting scraper statistics: {e}")
        return {"error": str(e)}
