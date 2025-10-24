"""
asyncpg connection pool management for high-performance writes.
"""

import asyncpg
from typing import Optional

from src.config import get_settings
from src.utils import get_logger

logger = get_logger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    """
    Initialize the asyncpg connection pool.
    Call this once at application startup.

    Returns:
        asyncpg.Pool: Connection pool instance
    """
    global _pool

    settings = get_settings()

    logger.info("Initializing asyncpg connection pool", extra={"url": settings.asyncpg_url})

    _pool = await asyncpg.create_pool(
        dsn=settings.asyncpg_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        timeout=settings.db_pool_timeout,
        command_timeout=60,  # Command timeout in seconds
        # Connection initialization callback
        server_settings={
            "application_name": "kirby_collector",
        },
    )

    logger.info(
        "asyncpg connection pool initialized successfully",
        extra={
            "min_size": settings.db_pool_min_size,
            "max_size": settings.db_pool_max_size,
        },
    )

    return _pool


async def close_pool() -> None:
    """
    Close the asyncpg connection pool.
    Call this at application shutdown.
    """
    global _pool

    if _pool:
        logger.info("Closing asyncpg connection pool")
        await _pool.close()
        _pool = None
        logger.info("asyncpg connection pool closed")


def get_pool() -> asyncpg.Pool:
    """
    Get the asyncpg connection pool.

    Returns:
        asyncpg.Pool: Connection pool instance

    Raises:
        RuntimeError: If pool not initialized
    """
    if _pool is None:
        raise RuntimeError("asyncpg pool not initialized. Call init_pool() first.")

    return _pool


async def execute_query(query: str, *args) -> str:
    """
    Execute a query and return the result status.

    Args:
        query: SQL query to execute
        *args: Query parameters

    Returns:
        str: Query execution status

    Raises:
        RuntimeError: If pool not initialized
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_one(query: str, *args) -> Optional[asyncpg.Record]:
    """
    Fetch a single row from the database.

    Args:
        query: SQL query to execute
        *args: Query parameters

    Returns:
        Optional[asyncpg.Record]: Query result or None

    Raises:
        RuntimeError: If pool not initialized
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query: str, *args) -> list[asyncpg.Record]:
    """
    Fetch all rows from the database.

    Args:
        query: SQL query to execute
        *args: Query parameters

    Returns:
        list[asyncpg.Record]: Query results

    Raises:
        RuntimeError: If pool not initialized
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)
