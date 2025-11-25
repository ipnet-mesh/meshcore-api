"""Logging configuration and setup."""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Custom text formatter with colors (if terminal supports it)."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        """
        Initialize formatter.

        Args:
            use_colors: Whether to use ANSI color codes
        """
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors."""
        if self.use_colors and record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


def setup_logging(level: str = "INFO", format_type: str = "json") -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ('json' or 'text')
    """
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)

    # Set formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter(use_colors=True)

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
