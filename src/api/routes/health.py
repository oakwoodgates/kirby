"""
Health check endpoints for monitoring system status.
"""

from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.config.settings import settings
from src.db.asyncpg_pool import get_pool

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.

    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }


@router.get("/health/database")
async def database_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Check database connection and get statistics.

    Args:
        db: Database session

    Returns:
        Database health information

    Raises:
        HTTPException: If database is unhealthy
    """
    try:
        # Test database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        # Get database version
        version_result = await db.execute(text("SELECT version()"))
        db_version = version_result.scalar()

        # Get connection pool stats
        pool = get_pool()
        pool_stats = {
            "size": pool.get_size() if pool else 0,
            "free": pool.get_idle_size() if pool else 0,
            "max_size": settings.DB_POOL_MAX_SIZE,
            "min_size": settings.DB_POOL_MIN_SIZE,
        }

        # Get table counts
        candle_count_result = await db.execute(text("SELECT COUNT(*) FROM candle"))
        candle_count = candle_count_result.scalar()

        funding_count_result = await db.execute(text("SELECT COUNT(*) FROM funding_rate"))
        funding_count = funding_count_result.scalar()

        oi_count_result = await db.execute(text("SELECT COUNT(*) FROM open_interest"))
        oi_count = oi_count_result.scalar()

        listing_count_result = await db.execute(text("SELECT COUNT(*) FROM listing WHERE is_active = true"))
        listing_count = listing_count_result.scalar()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "version": db_version.split()[1] if db_version else "unknown",
                "connected": True,
            },
            "connection_pool": pool_stats,
            "data_counts": {
                "candles": candle_count,
                "funding_rates": funding_count,
                "open_interest": oi_count,
                "active_listings": listing_count,
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
        )


@router.get("/health/detailed")
async def detailed_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Detailed health check with per-listing statistics.

    Args:
        db: Database session

    Returns:
        Detailed health information
    """
    try:
        # Get per-listing statistics
        candle_stats_query = text("""
            SELECT
                l.id,
                l.ccxt_symbol,
                COUNT(c.timestamp) as candle_count,
                MIN(c.timestamp) as earliest_candle,
                MAX(c.timestamp) as latest_candle
            FROM listing l
            LEFT JOIN candle c ON l.id = c.listing_id
            WHERE l.is_active = true
            GROUP BY l.id, l.ccxt_symbol
            ORDER BY l.id
        """)

        candle_stats_result = await db.execute(candle_stats_query)
        candle_stats = [
            {
                "listing_id": row[0],
                "symbol": row[1],
                "candle_count": row[2],
                "earliest_candle": row[3].isoformat() if row[3] else None,
                "latest_candle": row[4].isoformat() if row[4] else None,
                "data_freshness_seconds": (
                    (datetime.now(timezone.utc) - row[4]).total_seconds()
                    if row[4] else None
                ),
            }
            for row in candle_stats_result
        ]

        # Get database size
        db_size_query = text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size_result = await db.execute(db_size_query)
        db_size = db_size_result.scalar()

        # Get table sizes
        table_size_query = text("""
            SELECT
                tablename,
                pg_size_pretty(pg_total_relation_size('public.'||tablename))
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size('public.'||tablename) DESC
            LIMIT 10
        """)
        table_size_result = await db.execute(table_size_query)
        table_sizes = {row[0]: row[1] for row in table_size_result}

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "listings": candle_stats,
            "database": {
                "size": db_size,
                "table_sizes": table_sizes,
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
        )
