"""
Custom exceptions for the Kirby application.
"""


class KirbyException(Exception):
    """Base exception for all Kirby application errors."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class CollectorException(KirbyException):
    """Exception raised by data collectors."""

    pass


class DatabaseException(KirbyException):
    """Exception raised by database operations."""

    pass


class ValidationException(KirbyException):
    """Exception raised during data validation."""

    pass


class BackfillException(KirbyException):
    """Exception raised during historical data backfill."""

    pass


class ExchangeException(KirbyException):
    """Exception raised when interacting with exchanges."""

    pass
