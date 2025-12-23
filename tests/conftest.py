"""
Pytest configuration and shared fixtures for MediaFusion tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator

from db.schemas import UserData
from db.enums import MediaType


@pytest.fixture
def mock_user_data():
    """Create a mock UserData object for testing."""
    return UserData(
        selected_catalogs=[],
        torrent_sorting_priority=[],
        language_sorting=[],
        nudity_filter=["Disable"],
        certification_filter=["Disable"],
        contribution_streams=False,
    )


@pytest.fixture
def mock_async_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.getex = AsyncMock(return_value=None)
    redis_client.pipeline = MagicMock()
    return redis_client
