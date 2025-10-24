"""
SQLAlchemy async session management for database queries.
Used by the API and services for reading data.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import get_settings
from src.utils import get_logger

logger = get_logger(__name__)

# Global engine and session maker
_engine = None
_async_session_maker = None


def init_db() -> None:
    """
    Initialize the SQLAlchemy async engine and session maker.
    Call this once at application startup.
    """
    global _engine, _async_session_maker

    settings = get_settings()

    logger.info("Initializing SQLAlchemy async engine", extra={"url": str(settings.database_url)})

    # Create async engine
    _engine = create_async_engine(
        str(settings.database_url),
        echo=settings.is_development,  # Log SQL queries in development
        pool_pre_ping=True,  # Verify connections before using
        pool_size=settings.db_pool_min_size,
        max_overflow=settings.db_pool_max_size - settings.db_pool_min_size,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )

    # Create session maker
    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Don't expire objects after commit
        autoflush=False,  # Don't auto-flush before queries
        autocommit=False,
    )

    logger.info("SQLAlchemy async engine initialized successfully")


async def close_db() -> None:
    """
    Close the SQLAlchemy async engine.
    Call this at application shutdown.
    """
    global _engine

    if _engine:
        logger.info("Closing SQLAlchemy async engine")
        await _engine.dispose()
        _engine = None
        logger.info("SQLAlchemy async engine closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async SQLAlchemy session.

    Usage:
        async with get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

    Yields:
        AsyncSession: Database session
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
