"""
Tests for custom exception classes.
"""
import pytest
from utils.exceptions import (
    MediaFusionException,
    NotFoundError,
    DatabaseError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
)


class TestMediaFusionException:
    """Test cases for MediaFusionException base class."""

    def test_exception_creation(self):
        """Test basic exception creation."""
        exc = MediaFusionException("Test message")
        assert exc.message == "Test message"
        assert exc.error_code == "MediaFusionException"
        assert exc.details == {}
        assert exc.original_exception is None

    def test_exception_with_error_code(self):
        """Test exception with custom error code."""
        exc = MediaFusionException("Test message", error_code="CUSTOM_ERROR")
        assert exc.error_code == "CUSTOM_ERROR"

    def test_exception_with_details(self):
        """Test exception with details."""
        details = {"key": "value", "number": 123}
        exc = MediaFusionException("Test message", details=details)
        assert exc.details == details

    def test_exception_with_original_exception(self):
        """Test exception with original exception."""
        original = ValueError("Original error")
        exc = MediaFusionException("Test message", original_exception=original)
        assert exc.original_exception == original

    def test_exception_to_dict(self):
        """Test exception to dictionary conversion."""
        exc = MediaFusionException(
            "Test message",
            error_code="TEST_ERROR",
            details={"key": "value"},
        )
        result = exc.to_dict()
        assert result["error"] == "TEST_ERROR"
        assert result["message"] == "Test message"
        assert result["details"] == {"key": "value"}


class TestNotFoundError:
    """Test cases for NotFoundError."""

    def test_not_found_error_creation(self):
        """Test NotFoundError creation."""
        exc = NotFoundError("Resource not found")
        assert isinstance(exc, MediaFusionException)
        assert exc.message == "Resource not found"


class TestDatabaseError:
    """Test cases for DatabaseError."""

    def test_database_error_creation(self):
        """Test DatabaseError creation."""
        original = Exception("DB connection failed")
        exc = DatabaseError(
            "Database operation failed",
            original_exception=original,
        )
        assert isinstance(exc, MediaFusionException)
        assert exc.original_exception == original


class TestValidationError:
    """Test cases for ValidationError."""

    def test_validation_error_creation(self):
        """Test ValidationError creation."""
        exc = ValidationError("Invalid input", details={"field": "email"})
        assert isinstance(exc, MediaFusionException)
        assert exc.details == {"field": "email"}


class TestAuthenticationError:
    """Test cases for AuthenticationError."""

    def test_authentication_error_creation(self):
        """Test AuthenticationError creation."""
        exc = AuthenticationError("Invalid credentials")
        assert isinstance(exc, MediaFusionException)
        assert exc.message == "Invalid credentials"


class TestAuthorizationError:
    """Test cases for AuthorizationError."""

    def test_authorization_error_creation(self):
        """Test AuthorizationError creation."""
        exc = AuthorizationError("Access denied")
        assert isinstance(exc, MediaFusionException)
        assert exc.message == "Access denied"
