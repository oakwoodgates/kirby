"""
FastAPI dependencies for database sessions and other shared resources.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage:
        @router.get("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_db_session)):
            # Use session here
            pass
    """
    session = await get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
