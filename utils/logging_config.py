"""
Structured logging configuration for MediaFusion.
Provides JSON-formatted logging for better log analysis and monitoring.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from db.config import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add process/thread info
        log_data["process_id"] = record.process
        log_data["thread_id"] = record.thread
        
        # Add pathname if it's different from module
        if record.pathname:
            log_data["pathname"] = record.pathname
        
        return json.dumps(log_data, default=str)


class StructuredFormatter(logging.Formatter):
    """
    Structured formatter that outputs logs in a more readable format
    while still maintaining structure for parsing.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record in structured format."""
        parts = [
            f"[{datetime.utcnow().isoformat()}Z]",
            f"[{record.levelname:8s}]",
            f"[{record.name}]",
            f"[{record.module}:{record.funcName}:{record.lineno}]",
            record.getMessage(),
        ]
        
        if record.exc_info:
            parts.append(f"\n{self.formatException(record.exc_info)}")
        
        return " ".join(parts)


def setup_logging(use_json: Optional[bool] = None):
    """
    Setup logging configuration for the application.
    
    Args:
        use_json: Whether to use JSON formatting. If None, uses settings value.
    """
    # Determine if we should use JSON logging
    if use_json is None:
        # Use JSON logging if LOGGING_FORMAT env var is set to "json"
        # Otherwise use structured format
        use_json = getattr(settings, "logging_format", "structured") == "json"
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.logging_level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.logging_level.upper(), logging.INFO))
    
    # Set formatter based on configuration
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = StructuredFormatter(
            fmt="%(levelname)s::%(asctime)s::%(pathname)s::%(lineno)d - %(message)s",
            datefmt="%d-%b-%y %H:%M:%S",
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set levels for noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)
