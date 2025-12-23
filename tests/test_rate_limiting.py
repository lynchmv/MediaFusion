"""
Tests for rate limiting functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch

from api.middleware import RateLimitMiddleware
from utils.const import (
    RATE_LIMIT_DEFAULT_LIMIT,
    RATE_LIMIT_DEFAULT_WINDOW,
    RATE_LIMIT_CATALOG_LIMIT,
    RATE_LIMIT_CATALOG_WINDOW,
)


class TestRateLimitConstants:
    """Test rate limiting constants."""

    def test_rate_limit_constants_exist(self):
        """Test that rate limit constants are defined."""
        assert RATE_LIMIT_DEFAULT_LIMIT > 0
        assert RATE_LIMIT_DEFAULT_WINDOW > 0
        assert RATE_LIMIT_CATALOG_LIMIT > 0
        assert RATE_LIMIT_CATALOG_WINDOW > 0

    def test_rate_limit_constants_are_reasonable(self):
        """Test that rate limit values are reasonable."""
        # Default should be less restrictive than catalog
        assert RATE_LIMIT_DEFAULT_LIMIT <= RATE_LIMIT_CATALOG_LIMIT
        # Windows should be positive
        assert RATE_LIMIT_DEFAULT_WINDOW > 0
        assert RATE_LIMIT_CATALOG_WINDOW > 0


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_initialization(self):
        """Test that rate limit middleware can be initialized."""
        middleware = RateLimitMiddleware(MagicMock())
        assert middleware is not None

    def test_rate_limit_identifier_generation(self):
        """Test rate limit identifier generation."""
        from api.middleware import RateLimitMiddleware
        from db.schemas import UserData
        
        user_data = UserData(
            selected_catalogs=[],
            torrent_sorting_priority=[],
            language_sorting=[],
            nudity_filter=[],
            certification_filter=[],
        )
        
        identifier = RateLimitMiddleware.generate_identifier("127.0.0.1", user_data)
        assert identifier is not None
        assert len(identifier) > 0
