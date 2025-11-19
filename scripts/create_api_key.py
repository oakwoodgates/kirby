"""
Create a new API key for an existing user.
"""
import asyncio
import hashlib
import secrets
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import get_session_factory, get_sqlalchemy_engine
from src.db.models import APIKey, User


def generate_api_key() -> tuple[str, str, str]:
    """Generate a secure API key.

    Returns:
        Tuple of (api_key, key_hash, key_prefix)
    """
    # Generate random key (40 hex characters)
    api_key = "kb_" + secrets.token_hex(20)

    # Hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Prefix for display (first 10 characters)
    key_prefix = api_key[:10]

    return api_key, key_hash, key_prefix


async def create_key_for_user(
    session: AsyncSession,
    username: str,
    name: str = "CLI Generated Key",
) -> tuple[User, str]:
    """
    Create a new API key for the specified user.

    Args:
        session: Database session
        username: Username to create key for
        name: Name/description for the API key

    Returns:
        Tuple of (user, plaintext_api_key)

    Raises:
        ValueError: If user not found
    """
    # Find the user
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"User '{username}' not found")

    if not user.is_active:
        raise ValueError(f"User '{username}' is inactive")

    # Generate API key
    api_key, key_hash, key_prefix = generate_api_key()

    # Create API key record
    api_key_obj = APIKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        is_active=True,
        rate_limit=10000 if user.is_admin else 1000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(api_key_obj)
    await session.flush()
    await session.refresh(api_key_obj)

    return user, api_key


async def create_api_key(
    username: str = "admin",
    name: str = "CLI Generated Key",
) -> tuple[bool, str]:
    """
    Main function to create API key.

    Returns:
        Tuple of (success, api_key_or_error_message)
    """
    engine = get_sqlalchemy_engine()
    session_maker = get_session_factory()

    try:
        async with session_maker() as session:
            try:
                user, api_key = await create_key_for_user(session, username, name)
                await session.commit()
                return True, api_key
            except ValueError as e:
                await session.rollback()
                return False, str(e)
    finally:
        await engine.dispose()


def print_success(username: str, api_key: str):
    """Print success message with API key."""
    print()
    print("=" * 80)
    print("✅  API KEY CREATED SUCCESSFULLY")
    print("=" * 80)
    print()
    print(f"👤  Username: {username}")
    print()
    print("🔑  API KEY (SAVE THIS IMMEDIATELY - IT WILL NOT BE SHOWN AGAIN):")
    print()
    print(f"    {api_key}")
    print()
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Save the API key in a secure location")
    print("  2. Test the API key:")
    print(f"     curl -H 'Authorization: Bearer {api_key}' \\")
    print("       http://localhost:8000/starlistings")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    # Get username from command line or use default
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    name = sys.argv[2] if len(sys.argv) > 2 else "CLI Generated Key"

    success, result = asyncio.run(create_api_key(username, name))

    if success:
        print_success(username, result)
        sys.exit(0)
    else:
        print(f"\n❌  ERROR: {result}\n", file=sys.stderr)
        sys.exit(1)
