"""Authentication middleware for API key validation."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import APIKey, User
from src.utils.auth import hash_api_key, is_key_expired

# Security scheme for API key in Authorization header
security_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Container for authenticated user and API key information."""

    def __init__(self, user: User, api_key: APIKey):
        """Initialize authenticated user container.

        Args:
            user: The authenticated user
            api_key: The API key used for authentication
        """
        self.user = user
        self.api_key = api_key
        self.user_id = user.id
        self.api_key_id = api_key.id
        self.is_admin = user.is_admin
        self.rate_limit = api_key.rate_limit

    def __repr__(self) -> str:
        return f"<AuthenticatedUser(user_id={self.user_id}, api_key_id={self.api_key_id})>"


async def get_api_key_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[str]:
    """Extract API key from Authorization header.

    Expects: Authorization: Bearer kb_xxxxxxxxxxxxxxxxxxxx

    Args:
        credentials: HTTP credentials from Authorization header

    Returns:
        The API key string, or None if not provided
    """
    if credentials is None:
        return None

    # Credentials.credentials contains the token after "Bearer "
    return credentials.credentials


async def validate_api_key(
    session: AsyncSession,
    api_key: str,
) -> tuple[User, APIKey]:
    """Validate an API key and return the associated user and key.

    Args:
        session: Database session
        api_key: The API key to validate

    Returns:
        Tuple of (User, APIKey)

    Raises:
        HTTPException: If the API key is invalid, inactive, or expired
    """
    # Hash the provided key
    key_hash = hash_api_key(api_key)

    # Query for the API key with user (avoid lazy loading)
    query = (
        select(APIKey, User)
        .join(User, APIKey.user_id == User.id)
        .where(APIKey.key_hash == key_hash)
    )

    result = await session.execute(query)
    row = result.one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key_obj, user = row

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Check if API key is active
    if not api_key_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if API key is expired
    if is_key_expired(api_key_obj.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last_used_at timestamp
    api_key_obj.last_used_at = datetime.now(timezone.utc)
    await session.commit()

    return user, api_key_obj


async def get_current_user(
    session: AsyncSession,
    api_key: Optional[str] = Security(get_api_key_from_header),
) -> AuthenticatedUser:
    """Dependency to get the current authenticated user.

    This is the main authentication dependency for protected endpoints.

    Args:
        session: Database session (injected)
        api_key: API key from header (injected)

    Returns:
        AuthenticatedUser containing user and API key info

    Raises:
        HTTPException: If authentication fails
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide via Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, api_key_obj = await validate_api_key(session, api_key)

    return AuthenticatedUser(user=user, api_key=api_key_obj)


async def get_current_admin_user(
    current_user: AuthenticatedUser = Security(get_current_user),
) -> AuthenticatedUser:
    """Dependency to get the current authenticated admin user.

    Use this for endpoints that require admin privileges.

    Args:
        current_user: The authenticated user (injected)

    Returns:
        AuthenticatedUser with admin privileges

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user


async def get_optional_user(
    session: AsyncSession,
    api_key: Optional[str] = Security(get_api_key_from_header),
) -> Optional[AuthenticatedUser]:
    """Dependency to optionally get the current authenticated user.

    This allows endpoints to work with or without authentication.
    Useful for public endpoints that provide additional features for authenticated users.

    Args:
        session: Database session (injected)
        api_key: API key from header (injected)

    Returns:
        AuthenticatedUser if authenticated, None otherwise
    """
    if api_key is None:
        return None

    try:
        user, api_key_obj = await validate_api_key(session, api_key)
        return AuthenticatedUser(user=user, api_key=api_key_obj)
    except HTTPException:
        # Return None instead of raising error for optional auth
        return None
