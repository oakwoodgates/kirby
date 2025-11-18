"""Admin endpoints for user and API key management.

These endpoints are for administrative tasks like creating users,
generating API keys, and managing access. In production, these should
be protected by admin-only authentication.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_admin_user, AuthenticatedUser
from src.db.models import APIKey, User
from src.schemas.auth import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyResponse,
    UserCreate,
    UserResponse,
)
from src.utils.auth import calculate_expiration, generate_api_key, get_key_prefix, hash_api_key

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> UserResponse:
    """Create a new user.

    **Admin only**: This endpoint requires admin privileges.

    Args:
        user_data: User creation data
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        Created user

    Raises:
        HTTPException: If email or username already exists
    """
    # Check if email already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if username already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        is_admin=user_data.is_admin,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> List[UserResponse]:
    """List all users.

    **Admin only**: This endpoint requires admin privileges.

    Args:
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        List of all users
    """
    stmt = select(User).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    users = result.scalars().all()

    return [UserResponse.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> UserResponse:
    """Get user by ID.

    **Admin only**: This endpoint requires admin privileges.

    Args:
        user_id: User ID
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        User details

    Raises:
        HTTPException: If user not found
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.post(
    "/users/{user_id}/keys",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    user_id: int,
    key_data: APIKeyCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> APIKeyCreated:
    """Create a new API key for a user.

    **Admin only**: This endpoint requires admin privileges.

    **Important**: The full API key is only returned once. Save it securely!

    Args:
        user_id: User ID to create key for
        key_data: API key creation data
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        Created API key (includes full key - save it!)

    Raises:
        HTTPException: If user not found
    """
    # Verify user exists
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = get_key_prefix(api_key)

    # Calculate expiration if provided
    expires_at = None
    if key_data.expires_in_days:
        expires_at = calculate_expiration(key_data.expires_in_days)

    # Create API key record
    api_key_obj = APIKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_data.name,
        rate_limit=key_data.rate_limit,
        expires_at=expires_at,
    )

    session.add(api_key_obj)
    await session.commit()
    await session.refresh(api_key_obj)

    # Return response with full key (only time it's shown!)
    return APIKeyCreated(
        id=api_key_obj.id,
        user_id=api_key_obj.user_id,
        key_prefix=api_key_obj.key_prefix,
        name=api_key_obj.name,
        is_active=api_key_obj.is_active,
        rate_limit=api_key_obj.rate_limit,
        expires_at=api_key_obj.expires_at,
        last_used_at=api_key_obj.last_used_at,
        created_at=api_key_obj.created_at,
        updated_at=api_key_obj.updated_at,
        key=api_key,  # Full key - only shown once!
    )


@router.get("/users/{user_id}/keys", response_model=List[APIKeyResponse])
async def list_user_api_keys(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> List[APIKeyResponse]:
    """List all API keys for a user.

    **Admin only**: This endpoint requires admin privileges.

    Args:
        user_id: User ID
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        List of API keys (without full key values)

    Raises:
        HTTPException: If user not found
    """
    # Verify user exists
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get all keys for user
    stmt = select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
    result = await session.execute(stmt)
    keys = result.scalars().all()

    return [APIKeyResponse.model_validate(key) for key in keys]


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> None:
    """Revoke (deactivate) an API key.

    **Admin only**: This endpoint requires admin privileges.

    This sets the key's `is_active` flag to False. The key is not deleted
    from the database to maintain audit trails.

    Args:
        key_id: API key ID to revoke
        session: Database session (injected)
        current_user: Authenticated admin user (injected)

    Raises:
        HTTPException: If API key not found
    """
    stmt = select(APIKey).where(APIKey.id == key_id)
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Deactivate the key (don't delete for audit trail)
    api_key.is_active = False
    await session.commit()
