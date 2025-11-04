"""
Export open interest data to CSV and Parquet formats.

This script exports historical open interest data for specified trading pairs,
optimized for AI/ML training and backtesting.

Usage:
    python -m scripts.export_oi --coin BTC --days 30
    python -m scripts.export_oi --coin BTC --days 90 --format parquet
    python -m scripts.export_oi --coin SOL --start-time 2025-10-01 --end-time 2025-11-01
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.db.models import Coin, Exchange, MarketType, QuoteCurrency, Starlisting, OpenInterest
from src.utils.export import (
    generate_filename,
    generate_metadata,
    save_metadata,
    export_to_csv,
    export_to_parquet,
    parse_time_range,
    print_export_summary,
)


async def get_starlisting_id(
    session: AsyncSession,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
) -> int | None:
    """
    Get starlisting ID for the specified parameters.

    Note: For open interest, we just need any starlisting for this trading pair
    since open interest is the same across all intervals.
    """
    stmt = (
        select(Starlisting.id)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .where(
            Exchange.name == exchange,
            Coin.symbol == coin.upper(),
            QuoteCurrency.symbol == quote.upper(),
            MarketType.name == market_type,
        )
        .limit(1)
    )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def export_open_interest(
    session: AsyncSession,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    start_time: datetime,
    end_time: datetime,
    output_dir: Path,
    export_formats: list[str],
) -> bool:
    """Export open interest data."""
    print(f"\nExporting {coin} open interest...")

    starlisting_id = await get_starlisting_id(session, exchange, coin, quote, market_type)

    if not starlisting_id:
        print(f"  ERROR: Trading pair not found for {exchange}/{coin}/{quote}/{market_type}")
        return False

    stmt = (
        select(OpenInterest)
        .where(
            OpenInterest.starlisting_id == starlisting_id,
            OpenInterest.time >= start_time,
            OpenInterest.time <= end_time,
        )
        .order_by(OpenInterest.time)
    )

    result = await session.execute(stmt)
    oi_records = result.scalars().all()

    if not oi_records:
        print(f"  WARNING: No open interest data found in specified time range")
        return False

    df = pd.DataFrame(
        [
            {
                "time": record.time,
                "open_interest": float(record.open_interest) if record.open_interest else None,
                "notional_value": float(record.notional_value) if record.notional_value else None,
                "day_base_volume": float(record.day_base_volume) if record.day_base_volume else None,
                "day_notional_volume": float(record.day_notional_volume) if record.day_notional_volume else None,
            }
            for record in oi_records
        ]
    )

    print(f"  Found {len(df):,} open interest snapshots")

    export_timestamp = datetime.now()
    csv_path = None
    parquet_path = None

    if "csv" in export_formats:
        csv_filename = generate_filename(
            "open_interest", exchange, coin, quote, market_type, None, "csv", export_timestamp
        )
        csv_path = output_dir / csv_filename
        csv_size = export_to_csv(df, csv_path)
        print(f"  Exported CSV: {csv_filename} ({csv_size / 1024 / 1024:.2f} MB)")

        metadata = generate_metadata(
            "open_interest", exchange, coin, quote, market_type, None,
            df["time"].min(), df["time"].max(), len(df), csv_size, "csv", export_timestamp,
        )
        save_metadata(metadata, csv_path.with_suffix(".json"))

    if "parquet" in export_formats:
        parquet_filename = generate_filename(
            "open_interest", exchange, coin, quote, market_type, None, "parquet", export_timestamp
        )
        parquet_path = output_dir / parquet_filename
        parquet_size = export_to_parquet(df, parquet_path)
        print(f"  Exported Parquet: {parquet_filename} ({parquet_size / 1024 / 1024:.2f} MB)")

        metadata = generate_metadata(
            "open_interest", exchange, coin, quote, market_type, None,
            df["time"].min(), df["time"].max(), len(df), parquet_size, "parquet", export_timestamp,
        )
        save_metadata(metadata, parquet_path.with_suffix(".json"))

    print_export_summary("open_interest", coin, None, len(df), csv_path, parquet_path, df["time"].min(), df["time"].max())
    return True


async def main():
    """Main entry point for open interest export."""
    parser = argparse.ArgumentParser(
        description="Export open interest data to CSV and Parquet formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.export_oi --coin BTC --days 30
  python -m scripts.export_oi --coin SOL --days 90 --format parquet
  python -m scripts.export_oi --coin BTC --start-time 2025-10-01 --end-time 2025-11-01
        """,
    )

    parser.add_argument("--coin", required=True, help="Coin symbol (e.g., BTC, ETH, SOL)")
    parser.add_argument("--exchange", default="hyperliquid", help="Exchange name (default: hyperliquid)")
    parser.add_argument("--quote", default="USD", help="Quote currency (default: USD)")
    parser.add_argument("--market-type", default="perps", help="Market type (default: perps)")

    time_group = parser.add_mutually_exclusive_group(required=True)
    time_group.add_argument("--days", type=int, help="Number of days to look back from now")
    time_group.add_argument("--start-time", help="Start time (ISO format or Unix timestamp)")

    parser.add_argument("--end-time", help="End time (ISO format or Unix timestamp)")
    parser.add_argument("--format", choices=["csv", "parquet", "both"], default="both")
    parser.add_argument("--output", type=Path, default=Path("exports"))
    parser.add_argument("--database", choices=["production", "training"], default="production", help="Database to export from (default: production)")

    args = parser.parse_args()

    if args.end_time and not args.start_time:
        parser.error("--end-time requires --start-time")

    try:
        start_time, end_time = parse_time_range(args.days, args.start_time, args.end_time)
    except ValueError as e:
        parser.error(str(e))

    export_formats = ["csv", "parquet"] if args.format == "both" else [args.format]
    args.output.mkdir(parents=True, exist_ok=True)

    # Select database URL based on argument
    db_url = (
        settings.training_database_url_str
        if args.database == "training"
        else settings.database_url_str
    )

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print(f"{'='*60}")
        print(f"Kirby Open Interest Data Export")
        print(f"{'='*60}")
        print(f"Database: {args.database}")
        print(f"Coin: {args.coin}")
        print(f"Exchange: {args.exchange}")
        print(f"Quote: {args.quote}")
        print(f"Market Type: {args.market_type}")
        print(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}")
        print(f"Formats: {', '.join(export_formats)}")
        print(f"Output: {args.output.absolute()}")
        print(f"{'='*60}\n")

        success = await export_open_interest(
            session, args.exchange, args.coin, args.quote, args.market_type,
            start_time, end_time, args.output, export_formats,
        )

        result_msg = "exported successfully" if success else "No data exported"
        print(f"\n{'='*60}")
        print(f"Export {'Complete' if success else 'Failed'}: {result_msg}")
        print(f"{'='*60}\n")

    await engine.dispose()
    return 0 if success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
