"""Authentication utilities for API key generation and validation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def generate_api_key() -> str:
    """Generate a secure random API key.

    Format: kb_<40 hex characters> (total 43 characters)
    Example: kb_1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t

    Returns:
        A secure random API key string
    """
    # Generate 20 random bytes (40 hex characters)
    random_bytes = secrets.token_bytes(20)
    hex_string = random_bytes.hex()

    # Prefix with 'kb_' (Kirby)
    return f"kb_{hex_string}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        api_key: The API key to hash

    Returns:
        The SHA-256 hash of the API key (64 hex characters)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_key_prefix(api_key: str) -> str:
    """Extract the prefix from an API key for identification.

    Returns the first 8 characters (kb_xxxxx) to help users identify keys.

    Args:
        api_key: The full API key

    Returns:
        The first 8 characters of the API key
    """
    return api_key[:8] if len(api_key) >= 8 else api_key


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against a stored hash.

    Args:
        provided_key: The API key provided by the user
        stored_hash: The stored SHA-256 hash

    Returns:
        True if the key matches the hash, False otherwise
    """
    return hash_api_key(provided_key) == stored_hash


def is_key_expired(expires_at: datetime | None) -> bool:
    """Check if an API key has expired.

    Args:
        expires_at: The expiration datetime (None means never expires)

    Returns:
        True if the key is expired, False otherwise
    """
    if expires_at is None:
        return False

    return datetime.now(timezone.utc) > expires_at


def calculate_expiration(days: int) -> datetime:
    """Calculate expiration datetime from days in the future.

    Args:
        days: Number of days until expiration

    Returns:
        Expiration datetime in UTC
    """
    return datetime.now(timezone.utc) + timedelta(days=days)
