#!/usr/bin/env python3
"""
Bootstrap script to create the first admin user and API key.

This script should only be run on initial deployment when no users exist.
It will:
1. Check if any users already exist (exit if they do)
2. Create an admin user
3. Generate a secure API key
4. Display the API key (ONCE - save it immediately!)

Usage:
    python -m scripts.bootstrap_admin

    Or with custom email:
    python -m scripts.bootstrap_admin --email admin@example.com --username admin
"""
import argparse
import asyncio
import hashlib
import secrets
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.connection import create_engine_and_session
from src.db.models import APIKey, User


async def check_existing_users(session: AsyncSession) -> int:
    """Check if any users already exist.

    Returns:
        Number of existing users
    """
    result = await session.execute(select(User))
    users = result.scalars().all()
    return len(users)


async def create_admin_user(
    session: AsyncSession,
    email: str,
    username: str,
) -> User:
    """Create an admin user.

    Args:
        session: Database session
        email: Admin email
        username: Admin username

    Returns:
        Created user

    Raises:
        ValueError: If email or username already exists
    """
    # Check if email exists
    result = await session.execute(
        select(User).where(User.email == email)
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Email '{email}' already exists")

    # Check if username exists
    result = await session.execute(
        select(User).where(User.username == username)
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Username '{username}' already exists")

    # Create user
    user = User(
        email=email,
        username=username,
        is_admin=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(user)
    await session.flush()
    await session.refresh(user)

    return user


def generate_api_key() -> tuple[str, str, str]:
    """Generate a secure API key.

    Returns:
        Tuple of (api_key, key_hash, key_prefix)
    """
    # Generate random key
    api_key = "kb_" + secrets.token_hex(20)

    # Hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Prefix for display
    key_prefix = api_key[:10]

    return api_key, key_hash, key_prefix


async def create_api_key(
    session: AsyncSession,
    user: User,
    name: str = "Bootstrap Admin Key",
) -> tuple[APIKey, str]:
    """Create an API key for a user.

    Args:
        session: Database session
        user: User to create key for
        name: Key name/description

    Returns:
        Tuple of (APIKey object, plaintext API key)
    """
    api_key, key_hash, key_prefix = generate_api_key()

    api_key_obj = APIKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        is_active=True,
        rate_limit=10000,  # High limit for admin
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(api_key_obj)
    await session.flush()
    await session.refresh(api_key_obj)

    return api_key_obj, api_key


async def bootstrap(
    email: str = "admin@localhost",
    username: str = "admin",
    force: bool = False,
) -> tuple[bool, str | None]:
    """Bootstrap the first admin user and API key.

    Args:
        email: Admin email
        username: Admin username
        force: Force creation even if users exist (dangerous!)

    Returns:
        Tuple of (success, api_key or error_message)
    """
    engine, session_maker = create_engine_and_session(str(settings.database_url))

    try:
        async with session_maker() as session:
            # Check for existing users
            user_count = await check_existing_users(session)

            if user_count > 0 and not force:
                return False, f"Database already has {user_count} user(s). Use --force to override (not recommended)."

            try:
                # Create admin user
                user = await create_admin_user(session, email, username)

                # Create API key
                api_key_obj, api_key = await create_api_key(session, user)

                # Commit transaction
                await session.commit()

                return True, api_key

            except ValueError as e:
                await session.rollback()
                return False, str(e)

    finally:
        await engine.dispose()


def print_success(email: str, username: str, api_key: str):
    """Print success message with API key.

    IMPORTANT: This is the ONLY place the plaintext API key is displayed.
    """
    print()
    print("=" * 80)
    print("✅  ADMIN USER CREATED SUCCESSFULLY")
    print("=" * 80)
    print()
    print(f"📧  Email:    {email}")
    print(f"👤  Username: {username}")
    print(f"🔐  Admin:    Yes")
    print()
    print("🔑  API KEY (SAVE THIS IMMEDIATELY - IT WILL NOT BE SHOWN AGAIN):")
    print()
    print(f"    {api_key}")
    print()
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Save the API key in a secure location (password manager)")
    print("  2. Test the API key:")
    print(f"     curl -H 'Authorization: Bearer {api_key}' \\")
    print("       https://your-server/starlistings")
    print()
    print("  3. Create additional users via admin API:")
    print("     curl -X POST https://your-server/admin/users \\")
    print(f"       -H 'Authorization: Bearer {api_key}' \\")
    print("       -H 'Content-Type: application/json' \\")
    print("       -d '{\"email\": \"user@example.com\", \"username\": \"user1\", \"is_admin\": false}'")
    print()
    print("=" * 80)
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bootstrap first admin user and API key"
    )
    parser.add_argument(
        "--email",
        default="admin@localhost",
        help="Admin email (default: admin@localhost)",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Admin username (default: admin)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force creation even if users exist (NOT RECOMMENDED)",
    )

    args = parser.parse_args()

    # Run bootstrap
    success, result = asyncio.run(
        bootstrap(args.email, args.username, args.force)
    )

    if success:
        print_success(args.email, args.username, result)
        sys.exit(0)
    else:
        print(f"\n❌  ERROR: {result}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
