"""
Custom exception classes for MediaFusion application.
Provides structured error handling with proper context and logging.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MediaFusionException(Exception):
    """Base exception class for all MediaFusion exceptions."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.original_exception = original_exception
        
        # Log the exception
        self._log_exception()
    
    def _log_exception(self):
        """Log the exception with context."""
        log_message = f"{self.error_code}: {self.message}"
        if self.details:
            log_message += f" | Details: {self.details}"
        if self.original_exception:
            log_message += f" | Original: {type(self.original_exception).__name__}"
        
        logger.error(log_message, exc_info=self.original_exception)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(MediaFusionException):
    """Raised when input validation fails."""
    pass


class AuthenticationError(MediaFusionException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(MediaFusionException):
    """Raised when authorization fails."""
    pass


class NotFoundError(MediaFusionException):
    """Raised when a requested resource is not found."""
    pass


class DatabaseError(MediaFusionException):
    """Raised when a database operation fails."""
    pass


class CacheError(MediaFusionException):
    """Raised when a cache operation fails."""
    pass


class ScraperError(MediaFusionException):
    """Raised when a scraper operation fails."""
    pass


class StreamingProviderError(MediaFusionException):
    """Raised when a streaming provider operation fails."""
    pass


class RateLimitError(MediaFusionException):
    """Raised when rate limit is exceeded."""
    pass


class ConfigurationError(MediaFusionException):
    """Raised when there's a configuration error."""
    pass
