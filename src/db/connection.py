"""
Database connection management for asyncpg and SQLAlchemy.
"""
import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings

# Global connection pool and engine instances
_asyncpg_pool: asyncpg.Pool | None = None
_sqlalchemy_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_asyncpg_pool() -> asyncpg.Pool:
    """
    Get or create the asyncpg connection pool.
    Used for high-performance bulk inserts.
    """
    global _asyncpg_pool

    if _asyncpg_pool is None:
        _asyncpg_pool = await asyncpg.create_pool(
            dsn=settings.asyncpg_url_str,
            min_size=5,
            max_size=settings.database_pool_size,
            command_timeout=60,
            max_queries=50000,
            max_cached_statement_lifetime=300,
        )

    return _asyncpg_pool


async def close_asyncpg_pool() -> None:
    """Close the asyncpg connection pool."""
    global _asyncpg_pool

    if _asyncpg_pool is not None:
        await _asyncpg_pool.close()
        _asyncpg_pool = None


def get_sqlalchemy_engine() -> AsyncEngine:
    """
    Get or create the SQLAlchemy async engine.
    Used for complex queries and ORM operations.
    """
    global _sqlalchemy_engine

    if _sqlalchemy_engine is None:
        _sqlalchemy_engine = create_async_engine(
            settings.database_url_str,
            echo=settings.is_development,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    return _sqlalchemy_engine


async def close_sqlalchemy_engine() -> None:
    """Close the SQLAlchemy engine."""
    global _sqlalchemy_engine

    if _sqlalchemy_engine is not None:
        await _sqlalchemy_engine.dispose()
        _sqlalchemy_engine = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the SQLAlchemy session factory."""
    global _session_factory

    if _session_factory is None:
        engine = get_sqlalchemy_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    return _session_factory


async def get_session() -> AsyncSession:
    """
    Get a new SQLAlchemy async session.

    Usage:
        async with get_session() as session:
            # Use session here
            pass
    """
    session_factory = get_session_factory()
    return session_factory()


async def init_db() -> None:
    """Initialize database connections."""
    await get_asyncpg_pool()
    get_sqlalchemy_engine()


async def close_db() -> None:
    """Close all database connections."""
    await close_asyncpg_pool()
    await close_sqlalchemy_engine()
