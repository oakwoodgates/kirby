"""
Structured logging configuration for Kirby.
"""
import logging
import sys
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger

from src.config.settings import settings


def setup_logging() -> None:
    """
    Set up structured logging for the application.

    Uses structlog for structured logging with JSON output in production,
    and pretty console output in development.
    """
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Processors for structlog
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_format == "json":
        # JSON logging for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Pretty console logging for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for standard logging."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        log_record["logger"] = record.name
        log_record["level"] = record.levelname
        log_record["timestamp"] = self.formatTime(record, self.datefmt)


def configure_uvicorn_logging() -> dict[str, Any]:
    """
    Configure logging for Uvicorn.

    Returns:
        Logging configuration dict for Uvicorn
    """
    log_level = settings.api_log_level.lower()

    if settings.log_format == "json":
        # JSON logging
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JSONFormatter,
                    "fmt": "%(timestamp)s %(level)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": log_level.upper(), "handlers": ["console"]},
            "loggers": {
                "uvicorn": {"level": log_level.upper(), "handlers": ["console"], "propagate": False},
                "uvicorn.error": {"level": log_level.upper()},
                "uvicorn.access": {"level": log_level.upper()},
            },
        }
    else:
        # Default Uvicorn logging
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s %(message)s",
                    "use_colors": True,
                },
                "access": {
                    "()": "uvicorn.logging.AccessFormatter",
                    "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
                "access": {
                    "formatter": "access",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": log_level.upper()},
                "uvicorn.error": {"level": log_level.upper()},
                "uvicorn.access": {"handlers": ["access"], "level": log_level.upper(), "propagate": False},
            },
        }
