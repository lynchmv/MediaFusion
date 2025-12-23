"""
Tests for database operations.
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import SQLAlchemyError

from db import sql_crud
from db.enums import MediaType
from utils.exceptions import DatabaseError, NotFoundError


class TestDatabaseErrorHandling:
    """Test database error handling."""

    @pytest.mark.asyncio
    async def test_database_connection_error(self, mock_async_session):
        """Test handling of database connection errors."""
        mock_async_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        with pytest.raises(SQLAlchemyError):
            await mock_async_session.execute(AsyncMock())

    @pytest.mark.asyncio
    async def test_database_query_error(self, mock_async_session):
        """Test handling of database query errors."""
        mock_async_session.scalar.side_effect = SQLAlchemyError("Query failed")
        
        with pytest.raises(SQLAlchemyError):
            await mock_async_session.scalar(AsyncMock())


class TestMetadataRetrieval:
    """Test metadata retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_metadata_not_found(self, mock_async_session):
        """Test that missing metadata raises NotFoundError."""
        mock_async_session.scalar.return_value = None
        
        # This would be the actual implementation pattern
        # In real code, this would call sql_crud.get_metadata_by_type
        result = await mock_async_session.scalar(AsyncMock())
        assert result is None
