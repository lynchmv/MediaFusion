"""
Shared HTTP client management for MediaFusion.
Provides reusable HTTP clients with proper connection pooling and configuration.
"""
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx

from db.config import settings

logger = logging.getLogger(__name__)

# Default timeout settings
DEFAULT_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 10.0

# Shared HTTP client instances
_shared_client: Optional[httpx.AsyncClient] = None
_shared_proxy_client: Optional[httpx.AsyncClient] = None


def get_shared_client() -> httpx.AsyncClient:
    """
    Get or create the shared async HTTP client.
    This client should be reused across the application for better performance.
    
    Returns:
        httpx.AsyncClient: Shared HTTP client instance
    """
    global _shared_client
    
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=DEFAULT_TIMEOUT,
                connect=DEFAULT_CONNECT_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            ),
            follow_redirects=True,
        )
        logger.debug("Created shared HTTP client")
    
    return _shared_client


def get_shared_proxy_client() -> httpx.AsyncClient:
    """
    Get or create the shared async HTTP client with proxy configuration.
    This client should be reused for requests that require proxy.
    
    Returns:
        httpx.AsyncClient: Shared HTTP client instance with proxy
    """
    global _shared_proxy_client
    
    if _shared_proxy_client is None:
        _shared_proxy_client = httpx.AsyncClient(
            proxy=settings.requests_proxy_url,
            timeout=httpx.Timeout(
                timeout=DEFAULT_TIMEOUT,
                connect=DEFAULT_CONNECT_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            ),
            follow_redirects=True,
        )
        logger.debug("Created shared HTTP client with proxy")
    
    return _shared_proxy_client


@asynccontextmanager
async def get_client(use_proxy: bool = False):
    """
    Context manager for getting HTTP client.
    Use this when you need a client that might need cleanup.
    
    Args:
        use_proxy: Whether to use proxy client
        
    Yields:
        httpx.AsyncClient: HTTP client instance
    """
    if use_proxy:
        client = get_shared_proxy_client()
    else:
        client = get_shared_client()
    
    yield client


async def close_clients():
    """
    Close all shared HTTP clients.
    Should be called during application shutdown.
    """
    global _shared_client, _shared_proxy_client
    
    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None
        logger.debug("Closed shared HTTP client")
    
    if _shared_proxy_client is not None:
        await _shared_proxy_client.aclose()
        _shared_proxy_client = None
        logger.debug("Closed shared proxy HTTP client")
