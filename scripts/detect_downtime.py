"""Detect data collection downtime by analyzing gaps in time-series data.

This script queries the production database (kirby) to find the most recent
data timestamp for each table (candles, funding_rates, open_interest) and
calculates the time gap from the current moment. This helps identify periods
when the collector was down and data was missed.

Usage:
    python -m scripts.detect_downtime
    docker compose exec collector python -m scripts.detect_downtime

Output:
    JSON object with downtime information for each table and starlisting.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.connection import get_async_session_maker
from src.db.models import Starlisting, Candle, FundingRate, OpenInterest, Exchange, Coin, QuoteCurrency, MarketType, Interval


async def get_last_timestamp(session: AsyncSession, table: Any, starlisting_id: int) -> datetime | None:
    """Get the most recent timestamp for a given table and starlisting.

    Args:
        session: Database session
        table: SQLAlchemy table model (Candle, FundingRate, or OpenInterest)
        starlisting_id: The starlisting ID to check

    Returns:
        Most recent timestamp or None if no data exists
    """
    result = await session.execute(
        select(func.max(table.time))
        .where(table.starlisting_id == starlisting_id)
    )
    return result.scalar_one_or_none()


async def get_active_starlistings(session: AsyncSession) -> list[dict[str, Any]]:
    """Get all active starlistings with their details.

    Returns:
        List of starlisting dictionaries with id, exchange, coin, quote, market_type, interval
    """
    result = await session.execute(
        select(
            Starlisting.id,
            Exchange.name.label("exchange"),
            Coin.symbol.label("coin"),
            QuoteCurrency.symbol.label("quote"),
            MarketType.name.label("market_type"),
            Interval.name.label("interval"),
        )
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .join(Interval, Starlisting.interval_id == Interval.id)
        .where(Starlisting.active == True)
        .order_by(Exchange.name, Coin.symbol, Interval.name)
    )

    starlistings = []
    for row in result:
        starlistings.append({
            "id": row.id,
            "exchange": row.exchange,
            "coin": row.coin,
            "quote": row.quote,
            "market_type": row.market_type,
            "interval": row.interval,
        })

    return starlistings


async def detect_downtime() -> dict[str, Any]:
    """Detect downtime by analyzing the most recent data timestamps.

    Returns:
        Dictionary with downtime information:
        {
            "current_time": ISO timestamp,
            "starlistings": [
                {
                    "id": 1,
                    "exchange": "hyperliquid",
                    "coin": "BTC",
                    "quote": "USD",
                    "market_type": "perps",
                    "interval": "1m",
                    "candles": {
                        "last_timestamp": ISO timestamp or null,
                        "gap_minutes": int,
                        "gap_hours": float,
                        "has_data": bool
                    },
                    "funding_rates": {...},
                    "open_interest": {...}
                }
            ],
            "summary": {
                "total_starlistings": int,
                "max_gap_minutes": int,
                "tables_with_gaps": list[str]
            }
        }
    """
    settings = get_settings()
    session_maker = get_async_session_maker(settings.database_url_str)

    current_time = datetime.now(timezone.utc)

    async with session_maker() as session:
        # Get all active starlistings
        starlistings = await get_active_starlistings(session)

        # For each starlisting, check last timestamp in each table
        results = []
        max_gap_minutes = 0
        tables_with_gaps = set()

        for star in starlistings:
            star_id = star["id"]

            # Check candles table
            candle_last = await get_last_timestamp(session, Candle, star_id)
            candle_gap_minutes = 0
            if candle_last:
                candle_gap_minutes = int((current_time - candle_last).total_seconds() / 60)
                if candle_gap_minutes > 5:  # More than 5 minutes is considered a gap
                    tables_with_gaps.add("candles")

            # Check funding_rates table (not interval-specific)
            funding_last = await get_last_timestamp(session, FundingRate, star_id)
            funding_gap_minutes = 0
            if funding_last:
                funding_gap_minutes = int((current_time - funding_last).total_seconds() / 60)
                if funding_gap_minutes > 5:
                    tables_with_gaps.add("funding_rates")

            # Check open_interest table (not interval-specific)
            oi_last = await get_last_timestamp(session, OpenInterest, star_id)
            oi_gap_minutes = 0
            if oi_last:
                oi_gap_minutes = int((current_time - oi_last).total_seconds() / 60)
                if oi_gap_minutes > 5:
                    tables_with_gaps.add("open_interest")

            # Track max gap
            max_gap_minutes = max(max_gap_minutes, candle_gap_minutes, funding_gap_minutes, oi_gap_minutes)

            results.append({
                "id": star_id,
                "exchange": star["exchange"],
                "coin": star["coin"],
                "quote": star["quote"],
                "market_type": star["market_type"],
                "interval": star["interval"],
                "candles": {
                    "last_timestamp": candle_last.isoformat() if candle_last else None,
                    "gap_minutes": candle_gap_minutes,
                    "gap_hours": round(candle_gap_minutes / 60, 2),
                    "has_data": candle_last is not None,
                },
                "funding_rates": {
                    "last_timestamp": funding_last.isoformat() if funding_last else None,
                    "gap_minutes": funding_gap_minutes,
                    "gap_hours": round(funding_gap_minutes / 60, 2),
                    "has_data": funding_last is not None,
                },
                "open_interest": {
                    "last_timestamp": oi_last.isoformat() if oi_last else None,
                    "gap_minutes": oi_gap_minutes,
                    "gap_hours": round(oi_gap_minutes / 60, 2),
                    "has_data": oi_last is not None,
                },
            })

    return {
        "current_time": current_time.isoformat(),
        "starlistings": results,
        "summary": {
            "total_starlistings": len(starlistings),
            "max_gap_minutes": max_gap_minutes,
            "max_gap_hours": round(max_gap_minutes / 60, 2),
            "tables_with_gaps": sorted(list(tables_with_gaps)),
        },
    }


async def main() -> None:
    """Main entry point for the script."""
    try:
        downtime_info = await detect_downtime()

        # Output as JSON
        print(json.dumps(downtime_info, indent=2))

        # Exit with status based on whether gaps were detected
        if downtime_info["summary"]["max_gap_minutes"] > 5:
            sys.exit(1)  # Gaps detected
        else:
            sys.exit(0)  # No significant gaps

    except Exception as e:
        error_output = {
            "error": str(e),
            "type": type(e).__name__,
        }
        print(json.dumps(error_output, indent=2), file=sys.stderr)
        sys.exit(2)  # Error occurred


if __name__ == "__main__":
    asyncio.run(main())
