"""
FastAPI dependency injection functions.

Provides database sessions, authentication, and other shared dependencies.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a SQLAlchemy async session.

    Yields:
        AsyncSession: Database session

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session
            pass
    """
    async with get_async_session() as session:
        yield session
