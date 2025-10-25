"""
Backfill orchestrator script for historical data ingestion.

This script runs backfill jobs for specified listings and date ranges.
Supports multi-interval backfilling (1m, 15m, 4h, 1d, etc.) based on
listing configuration.

It tracks progress in the backfill_job table and supports resumable operations.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.backfill.hyperliquid_backfiller import HyperliquidBackfiller
from src.db.asyncpg_pool import init_pool, close_pool, get_pool
from src.utils.interval_manager import IntervalManager
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def create_backfill_job(
    listing_id: int,
    data_type: str,
    start_date: datetime,
    end_date: datetime,
) -> int:
    """
    Create a backfill job record in the database.

    Args:
        listing_id: Database listing ID
        data_type: Type of data to backfill ('candles', 'funding_rates', 'open_interest')
        start_date: Start date for backfill
        end_date: End date for backfill

    Returns:
        Job ID
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """
            INSERT INTO backfill_job
            (listing_id, data_type, start_date, end_date, status, records_fetched)
            VALUES ($1, $2, $3, $4, 'pending', 0)
            RETURNING id
            """,
            listing_id, data_type, start_date, end_date
        )
    return job_id


async def update_backfill_job(
    job_id: int,
    status: str,
    records_fetched: Optional[int] = None,
    error_message: Optional[str] = None,
):
    """
    Update backfill job status and progress.

    Args:
        job_id: Job ID
        status: New status ('running', 'completed', 'failed')
        records_fetched: Number of records fetched
        error_message: Error message if failed
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if status == 'completed':
            await conn.execute(
                """
                UPDATE backfill_job
                SET status = $1,
                    records_fetched = COALESCE($2, records_fetched),
                    updated_at = now(),
                    completed_at = now()
                WHERE id = $3
                """,
                status, records_fetched, job_id
            )
        elif status == 'failed':
            await conn.execute(
                """
                UPDATE backfill_job
                SET status = $1,
                    error_message = $2,
                    updated_at = now()
                WHERE id = $3
                """,
                status, error_message, job_id
            )
        else:
            await conn.execute(
                """
                UPDATE backfill_job
                SET status = $1,
                    records_fetched = COALESCE($2, records_fetched),
                    updated_at = now()
                WHERE id = $3
                """,
                status, records_fetched, job_id
            )


async def get_listing_info(listing_id: int) -> dict:
    """
    Get listing information from database.

    Args:
        listing_id: Database listing ID

    Returns:
        Dictionary with listing info including collector_config
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT l.id, l.ccxt_symbol as symbol, l.collector_config, e.name as exchange_name
            FROM listing l
            JOIN exchange e ON l.exchange_id = e.id
            WHERE l.id = $1
            """,
            listing_id
        )
        if not row:
            raise ValueError(f"Listing {listing_id} not found")

        return dict(row)


async def run_backfill_for_listing(
    listing_id: int,
    data_types: List[str],
    start_date: datetime,
    end_date: datetime,
    intervals: Optional[List[str]] = None,
):
    """
    Run backfill for a specific listing across multiple intervals.

    Args:
        listing_id: Database listing ID
        data_types: List of data types to backfill ('candles', 'funding_rates', 'open_interest')
        start_date: Start date for backfill
        end_date: End date for backfill
        intervals: List of intervals to backfill (if None, read from collector_config)
    """
    # Get listing info
    listing_info = await get_listing_info(listing_id)
    logger.info(
        f"Starting backfill for listing {listing_id}: "
        f"{listing_info['symbol']} on {listing_info['exchange_name']}"
    )

    # Get intervals from collector_config if not specified
    if intervals is None and listing_info.get('collector_config'):
        config = listing_info['collector_config']
        # Try new format first (candle_intervals array), fallback to old format (candle_interval string)
        intervals = config.get('candle_intervals') or [config.get('candle_interval', '1m')]
        logger.info(f"Using intervals from config: {intervals}")
    elif intervals is None:
        # Default to 1m if no config
        intervals = ['1m']
        logger.info(f"No interval config found, defaulting to: {intervals}")

    # Validate intervals
    intervals = IntervalManager.validate_intervals(intervals)
    intervals_str = IntervalManager.format_interval_list(intervals)
    logger.info(f"Backfilling intervals: {intervals_str}")

    # Create backfiller instance
    if listing_info['exchange_name'].lower() == 'hyperliquid':
        backfiller = HyperliquidBackfiller(
            listing_id=listing_id,
            symbol=listing_info['symbol'],
            start_date=start_date,
            end_date=end_date,
        )
    else:
        logger.error(f"Unsupported exchange: {listing_info['exchange_name']}")
        return

    # Initialize backfiller
    await backfiller.initialize()

    try:
        # Run backfill for each data type
        for data_type in data_types:
            if data_type == 'candles':
                # Backfill each interval separately
                for interval in intervals:
                    # Create job record
                    job_id = await create_backfill_job(
                        listing_id=listing_id,
                        data_type=f'candles_{interval}',  # Track per-interval jobs
                        start_date=start_date,
                        end_date=end_date,
                    )
                    logger.info(f"Created backfill job {job_id} for {interval} candles")

                    try:
                        # Mark as running
                        await update_backfill_job(job_id, 'running')

                        # Execute backfill for this interval
                        count = await backfiller.backfill_candles(interval=interval)

                        # Mark as complete
                        await update_backfill_job(
                            job_id=job_id,
                            status='completed',
                            records_fetched=count,
                        )
                        logger.info(
                            f"Backfill job {job_id} completed: "
                            f"{count} {interval} candles fetched"
                        )

                    except Exception as e:
                        logger.error(f"Backfill failed for {interval} candles: {e}", exc_info=True)
                        await update_backfill_job(
                            job_id=job_id,
                            status='failed',
                            error_message=str(e),
                        )

            elif data_type == 'funding_rates':
                # Funding rates are not interval-specific
                job_id = await create_backfill_job(
                    listing_id=listing_id,
                    data_type='funding_rates',
                    start_date=start_date,
                    end_date=end_date,
                )
                logger.info(f"Created backfill job {job_id} for funding_rates")

                try:
                    await update_backfill_job(job_id, 'running')
                    count = await backfiller.backfill_funding_rates()
                    await update_backfill_job(
                        job_id=job_id,
                        status='completed',
                        records_fetched=count,
                    )
                    logger.info(f"Backfill job {job_id} completed: {count} funding rates fetched")

                except Exception as e:
                    logger.error(f"Backfill failed for funding rates: {e}", exc_info=True)
                    await update_backfill_job(
                        job_id=job_id,
                        status='failed',
                        error_message=str(e),
                    )

            elif data_type == 'open_interest':
                # Open interest is not interval-specific
                job_id = await create_backfill_job(
                    listing_id=listing_id,
                    data_type='open_interest',
                    start_date=start_date,
                    end_date=end_date,
                )
                logger.info(f"Created backfill job {job_id} for open_interest")

                try:
                    await update_backfill_job(job_id, 'running')
                    count = await backfiller.backfill_open_interest()
                    await update_backfill_job(
                        job_id=job_id,
                        status='completed',
                        records_fetched=count,
                    )
                    logger.info(f"Backfill job {job_id} completed: {count} open interest records fetched")

                except Exception as e:
                    logger.error(f"Backfill failed for open interest: {e}", exc_info=True)
                    await update_backfill_job(
                        job_id=job_id,
                        status='failed',
                        error_message=str(e),
                    )

    finally:
        # Cleanup backfiller
        await backfiller.cleanup()


async def main():
    """
    Main function to run backfill jobs.
    """
    setup_logging(log_level="INFO", log_format="text")
    logger.info("=== Starting Backfill Service ===")

    # Initialize database pool
    logger.info("Initializing database connection pool...")
    await init_pool()

    try:
        # Example: Backfill last 30 days for BTC and HYPE
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        logger.info(f"Backfill date range: {start_date} to {end_date}")

        # Backfill for BTC (listing_id=1)
        # Will automatically read intervals from collector_config
        logger.info("\n=== Backfilling BTC ===")
        await run_backfill_for_listing(
            listing_id=1,
            data_types=['candles', 'funding_rates'],  # Skip OI (not historical)
            start_date=start_date,
            end_date=end_date,
        )

        # Backfill for HYPE (listing_id=2)
        logger.info("\n=== Backfilling HYPE ===")
        await run_backfill_for_listing(
            listing_id=2,
            data_types=['candles', 'funding_rates'],
            start_date=start_date,
            end_date=end_date,
        )

        logger.info("\n=== Backfill Complete ===")

    except Exception as e:
        logger.error(f"Backfill service error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Close database pool
        logger.info("Closing database connection pool...")
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
