"""
Structured logging configuration for the Kirby application.
Supports both JSON and text formats with contextual information.
"""

import logging
import sys
from typing import Optional

from pythonjsonlogger import jsonlogger

from src.config import get_settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds standard fields to all log records.
    """

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Add contextual fields if present
        if hasattr(record, "listing_id"):
            log_record["listing_id"] = record.listing_id
        if hasattr(record, "exchange"):
            log_record["exchange"] = record.exchange
        if hasattr(record, "symbol"):
            log_record["symbol"] = record.symbol
        if hasattr(record, "collector_id"):
            log_record["collector_id"] = record.collector_id


def setup_logging(log_level: Optional[str] = None, log_format: Optional[str] = None) -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format ('json' or 'text')
    """
    settings = get_settings()
    level = log_level or settings.log_level
    format_type = log_format or settings.log_format

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.upper())

    # Set formatter based on format type
    if format_type.lower() == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.

    Args:
        name: Logger name (typically __name__ from the calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information to all log messages.
    Useful for adding listing_id, exchange, symbol, etc. to collector logs.
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Add extra fields to the log record."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_contextual_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with contextual information.

    Example:
        logger = get_contextual_logger(__name__, listing_id=1, exchange="hyperliquid")
        logger.info("Connected to exchange")  # Will include listing_id and exchange in logs

    Args:
        name: Logger name
        **context: Contextual key-value pairs to include in all log messages

    Returns:
        LoggerAdapter with contextual information
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
