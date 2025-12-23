"""
Tests for API main endpoints.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.main import app
from utils.exceptions import NotFoundError, DatabaseError
from db.enums import MediaType


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestExceptionHandling:
    """Test exception handling in API endpoints."""

    @pytest.mark.asyncio
    async def test_not_found_error_handler(self):
        """Test that NotFoundError returns 404 status."""
        exc = NotFoundError("Resource not found", details={"id": "123"})
        response = await app.exception_handler(
            type("Request", (), {"scope": {}})(),
            exc,
        )
        assert response.status_code == 404
        assert response.body is not None

    @pytest.mark.asyncio
    async def test_authentication_error_handler(self):
        """Test that AuthenticationError returns 401 status."""
        from utils.exceptions import AuthenticationError
        exc = AuthenticationError("Invalid credentials")
        response = await app.exception_handler(
            type("Request", (), {"scope": {}})(),
            exc,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validation_error_handler(self):
        """Test that ValidationError returns 422 status."""
        from utils.exceptions import ValidationError
        exc = ValidationError("Invalid input")
        response = await app.exception_handler(
            type("Request", (), {"scope": {}})(),
            exc,
        )
        assert response.status_code == 422


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint(self, client):
        """Test that health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
