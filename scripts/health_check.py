"""
Manual health check script for Kirby.

Usage:
    python -m scripts.health_check
"""
import asyncio
import sys
from datetime import timedelta

import structlog

from src.config.settings import settings
from src.db.connection import close_db, get_session, init_db
from src.db.repositories import CandleRepository, StarlistingRepository
from src.utils.helpers import utc_now
from src.utils.logging import setup_logging


async def check_database_connection() -> bool:
    """
    Check database connection.

    Returns:
        True if connected, False otherwise
    """
    logger = structlog.get_logger("kirby.health.database")

    try:
        session = await get_session()
        try:
            # Simple query to verify connection
            result = await session.execute("SELECT 1")
            result.scalar()
        finally:
            await session.close()

        logger.info("Database connection: OK")
        return True

    except Exception as e:
        logger.error("Database connection: FAILED", error=str(e))
        return False


async def check_data_freshness() -> dict[str, bool]:
    """
    Check data freshness for all starlistings.

    Returns:
        Dictionary mapping starlisting to freshness status
    """
    logger = structlog.get_logger("kirby.health.freshness")

    freshness = {}
    threshold = timedelta(seconds=settings.data_freshness_threshold)
    now = utc_now()

    try:
        session = await get_session()
        try:
            # Get all active starlistings
            starlisting_repo = StarlistingRepository(session)
            starlistings = await starlisting_repo.get_active_starlistings()

            for starlisting in starlistings:
                # Get latest candle
                candle_session = await get_session()
                try:
                    candle_repo = CandleRepository(candle_session)
                    latest = await candle_repo.get_latest_candle(
                        candle_session,
                        starlisting.id,
                    )
                finally:
                    await candle_session.close()

                if not latest:
                    freshness[f"{starlisting.exchange.name}/{starlisting.coin.symbol}/{starlisting.interval.name}"] = False
                    logger.warning(
                        "No candles found",
                        exchange=starlisting.exchange.name,
                        coin=starlisting.coin.symbol,
                        interval=starlisting.interval.name,
                    )
                else:
                    age = now - latest.time
                    is_fresh = age <= threshold

                    freshness[f"{starlisting.exchange.name}/{starlisting.coin.symbol}/{starlisting.interval.name}"] = is_fresh

                    if not is_fresh:
                        logger.warning(
                            "Stale data detected",
                            exchange=starlisting.exchange.name,
                            coin=starlisting.coin.symbol,
                            interval=starlisting.interval.name,
                            age_seconds=int(age.total_seconds()),
                            threshold_seconds=settings.data_freshness_threshold,
                        )
                    else:
                        logger.info(
                            "Data is fresh",
                            exchange=starlisting.exchange.name,
                            coin=starlisting.coin.symbol,
                            interval=starlisting.interval.name,
                            age_seconds=int(age.total_seconds()),
                        )
        finally:
            await session.close()

        return freshness

    except Exception as e:
        logger.error("Data freshness check failed", error=str(e), exc_info=True)
        return {}


async def run_health_check() -> bool:
    """
    Run comprehensive health check.

    Returns:
        True if all checks pass, False otherwise
    """
    logger = structlog.get_logger("kirby.health")

    logger.info("Running Kirby health check")

    # Initialize database
    await init_db()

    all_healthy = True

    # Check database connection
    db_healthy = await check_database_connection()
    all_healthy = all_healthy and db_healthy

    # Check data freshness
    freshness = await check_data_freshness()
    if freshness:
        fresh_count = sum(1 for v in freshness.values() if v)
        total_count = len(freshness)

        logger.info(
            "Data freshness check complete",
            fresh_count=fresh_count,
            total_count=total_count,
        )

        if fresh_count < total_count:
            all_healthy = False

    # Close database
    await close_db()

    # Final status
    if all_healthy:
        logger.info("✓ Health check PASSED")
    else:
        logger.warning("✗ Health check FAILED")

    return all_healthy


async def main() -> None:
    """Main entry point."""
    # Set up logging
    setup_logging()

    # Run health check
    healthy = await run_health_check()

    # Exit with appropriate code
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    asyncio.run(main())
