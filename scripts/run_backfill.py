"""
Backfill orchestrator script for historical data ingestion.

This script runs backfill jobs for specified listings and date ranges.
It tracks progress in the backfill_job table and supports resumable operations.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.backfill.hyperliquid_backfiller import HyperliquidBackfiller
from src.db.asyncpg_pool import init_pool, close_pool, get_pool
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
        Dictionary with listing info
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT l.id, l.symbol, l.exchange_symbol, e.name as exchange_name
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
    batch_size: int = 1000,
):
    """
    Run backfill for a specific listing.

    Args:
        listing_id: Database listing ID
        data_types: List of data types to backfill
        start_date: Start date for backfill
        end_date: End date for backfill
        batch_size: Number of records to fetch per batch
    """
    # Get listing info
    listing_info = await get_listing_info(listing_id)
    logger.info(
        f"Starting backfill for listing {listing_id}: "
        f"{listing_info['symbol']} on {listing_info['exchange_name']}"
    )

    # Create backfiller instance
    if listing_info['exchange_name'].lower() == 'hyperliquid':
        backfiller = HyperliquidBackfiller(
            listing_id=listing_id,
            symbol=listing_info['symbol'],
            start_date=start_date,
            end_date=end_date,
            batch_size=batch_size,
        )
    else:
        logger.error(f"Unsupported exchange: {listing_info['exchange_name']}")
        return

    # Create job records for each data type
    job_ids = {}
    for data_type in data_types:
        job_id = await create_backfill_job(
            listing_id=listing_id,
            data_type=data_type,
            start_date=start_date,
            end_date=end_date,
        )
        job_ids[data_type] = job_id
        logger.info(f"Created backfill job {job_id} for {data_type}")

    # Run backfill
    try:
        # Mark all jobs as running
        for job_id in job_ids.values():
            await update_backfill_job(job_id, 'running')

        # Execute backfill
        results = await backfiller.run_backfill(data_types=data_types)

        # Update job statuses
        for data_type, records_count in results.items():
            job_id = job_ids[data_type]
            await update_backfill_job(
                job_id=job_id,
                status='completed',
                records_fetched=records_count,
            )
            logger.info(
                f"Backfill job {job_id} completed: "
                f"{records_count} {data_type} records fetched"
            )

    except Exception as e:
        logger.error(f"Backfill failed for listing {listing_id}: {e}", exc_info=True)

        # Mark jobs as failed
        for data_type, job_id in job_ids.items():
            await update_backfill_job(
                job_id=job_id,
                status='failed',
                error_message=str(e),
            )


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
        logger.info("\n=== Backfilling BTC ===")
        await run_backfill_for_listing(
            listing_id=1,
            data_types=['candles', 'funding_rates'],  # Skip OI (not historical)
            start_date=start_date,
            end_date=end_date,
            batch_size=1000,
        )

        # Backfill for HYPE (listing_id=2)
        logger.info("\n=== Backfilling HYPE ===")
        await run_backfill_for_listing(
            listing_id=2,
            data_types=['candles', 'funding_rates'],
            start_date=start_date,
            end_date=end_date,
            batch_size=1000,
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
