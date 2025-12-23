"""
Custom exceptions for streaming provider operations.
"""
from typing import Optional, Dict, Any


class ProviderException(Exception):
    """
    Base exception for streaming provider errors.
    
    Attributes:
        message: Error message
        video_file_name: Name of the video file that caused the error
        provider: Name of the streaming provider
        error_code: Optional error code for programmatic handling
        details: Optional dictionary with additional error details
    """
    
    def __init__(
        self,
        message: str,
        video_file_name: str,
        provider: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.video_file_name = video_file_name
        self.provider = provider
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "error": self.error_code,
            "message": self.message,
            "video_file_name": self.video_file_name,
        }
        if self.provider:
            result["provider"] = self.provider
        if self.details:
            result["details"] = self.details
        return result


class ProviderAuthenticationError(ProviderException):
    """Raised when provider authentication fails."""
    pass


class ProviderRateLimitError(ProviderException):
    """Raised when provider rate limit is exceeded."""
    pass


class ProviderQuotaExceededError(ProviderException):
    """Raised when provider quota is exceeded."""
    pass


class ProviderFileNotFoundError(ProviderException):
    """Raised when requested file is not found in provider."""
    pass
