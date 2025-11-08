"""
Export candle (OHLCV) data to CSV and Parquet formats.

This script exports historical candle data for specified trading pairs and intervals,
optimized for AI/ML training and backtesting.

Usage:
    python -m scripts.export_candles --coin BTC --intervals 1m --days 30
    python -m scripts.export_candles --coin BTC --intervals all --days 90 --format parquet
    python -m scripts.export_candles --coin SOL --intervals 1m,15m,4h --start-time 2025-10-01 --end-time 2025-11-01
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
from src.db.models import Coin, Exchange, Interval, MarketType, QuoteCurrency, Starlisting, Candle
from src.utils.database_helpers import get_starlisting_params
from src.utils.export import (
    generate_filename,
    generate_metadata,
    save_metadata,
    export_to_csv,
    export_to_parquet,
    parse_time_range,
    print_export_summary,
    parse_intervals,
)


async def get_starlisting_id(
    session: AsyncSession,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str,
) -> int | None:
    """
    Get starlisting ID for the specified parameters.

    Args:
        session: Database session
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type
        interval: Interval name

    Returns:
        Starlisting ID or None if not found
    """
    stmt = (
        select(Starlisting.id)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .join(Interval, Starlisting.interval_id == Interval.id)
        .where(
            Exchange.name == exchange,
            Coin.symbol == coin.upper(),
            QuoteCurrency.symbol == quote.upper(),
            MarketType.name == market_type,
            Interval.name == interval,
        )
    )

    result = await session.execute(stmt)
    starlisting_id = result.scalar_one_or_none()

    return starlisting_id


async def export_candles_for_interval(
    session: AsyncSession,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
    output_dir: Path,
    export_formats: list[str],
) -> bool:
    """
    Export candle data for a single interval.

    Args:
        session: Database session
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type
        interval: Interval name
        start_time: Start time for data
        end_time: End time for data
        output_dir: Output directory
        export_formats: List of formats to export ('csv', 'parquet', or both)

    Returns:
        True if export successful, False otherwise
    """
    print(f"\nExporting {coin} {interval} candles...")

    # Get starlisting ID
    starlisting_id = await get_starlisting_id(
        session, exchange, coin, quote, market_type, interval
    )

    if not starlisting_id:
        print(f"  ERROR: Starlisting not found for {exchange}/{coin}/{quote}/{market_type}/{interval}")
        return False

    # Query candle data
    stmt = (
        select(Candle)
        .where(
            Candle.starlisting_id == starlisting_id,
            Candle.time >= start_time,
            Candle.time <= end_time,
        )
        .order_by(Candle.time)
    )

    result = await session.execute(stmt)
    candles = result.scalars().all()

    if not candles:
        print(f"  WARNING: No candle data found for {interval} in specified time range")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(
        [
            {
                "time": candle.time,
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
                "num_trades": candle.num_trades,
            }
            for candle in candles
        ]
    )

    print(f"  Found {len(df):,} candles")

    # Export timestamp for consistent filenames
    export_timestamp = datetime.now()

    # Export to CSV if requested
    csv_path = None
    if "csv" in export_formats:
        csv_filename = generate_filename(
            "candles", exchange, coin, quote, market_type, interval, "csv", export_timestamp
        )
        csv_path = output_dir / csv_filename
        csv_size = export_to_csv(df, csv_path)
        print(f"  Exported CSV: {csv_filename} ({csv_size / 1024 / 1024:.2f} MB)")

        # Save metadata
        metadata = generate_metadata(
            "candles",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            df["time"].min(),
            df["time"].max(),
            len(df),
            csv_size,
            "csv",
            export_timestamp,
        )
        metadata_path = csv_path.with_suffix(".json")
        save_metadata(metadata, metadata_path)

    # Export to Parquet if requested
    parquet_path = None
    if "parquet" in export_formats:
        parquet_filename = generate_filename(
            "candles", exchange, coin, quote, market_type, interval, "parquet", export_timestamp
        )
        parquet_path = output_dir / parquet_filename
        parquet_size = export_to_parquet(df, parquet_path)
        print(f"  Exported Parquet: {parquet_filename} ({parquet_size / 1024 / 1024:.2f} MB)")

        # Save metadata
        metadata = generate_metadata(
            "candles",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            df["time"].min(),
            df["time"].max(),
            len(df),
            parquet_size,
            "parquet",
            export_timestamp,
        )
        metadata_path = parquet_path.with_suffix(".json")
        save_metadata(metadata, metadata_path)

    # Print summary
    print_export_summary(
        "candles",
        coin,
        interval,
        len(df),
        csv_path,
        parquet_path,
        df["time"].min(),
        df["time"].max(),
    )

    return True


async def get_available_intervals(session: AsyncSession) -> list[str]:
    """Get list of all available intervals."""
    stmt = select(Interval.name).order_by(Interval.seconds)
    result = await session.execute(stmt)
    intervals = result.scalars().all()
    return list(intervals)


async def main():
    """Main entry point for candle export."""
    parser = argparse.ArgumentParser(
        description="Export candle (OHLCV) data to CSV and Parquet formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export BTC 1m candles for last 30 days (both formats)
  python -m scripts.export_candles --coin BTC --intervals 1m --days 30

  # Export SOL all intervals for last 90 days as Parquet only
  python -m scripts.export_candles --coin SOL --intervals all --days 90 --format parquet

  # Export BTC specific intervals for custom date range
  python -m scripts.export_candles --coin BTC --intervals 1m,15m,4h \\
      --start-time 2025-10-01 --end-time 2025-11-01

  # Export to custom directory
  python -m scripts.export_candles --coin BTC --intervals 1m --days 7 \\
      --output /path/to/exports
        """,
    )

    # Required arguments
    parser.add_argument(
        "--coin",
        required=True,
        help="Coin symbol (e.g., BTC, ETH, SOL)",
    )

    # Interval arguments
    parser.add_argument(
        "--intervals",
        required=True,
        help="Comma-separated intervals or 'all' (e.g., '1m', '1m,15m,4h', 'all')",
    )

    # Optional trading pair parameters
    parser.add_argument(
        "--exchange",
        default=None,
        help="Exchange name (auto-detected from database if not specified)",
    )
    parser.add_argument(
        "--quote",
        default=None,
        help="Quote currency (auto-detected from database if not specified)",
    )
    parser.add_argument(
        "--market-type",
        default=None,
        help="Market type (auto-detected from database if not specified)",
    )

    # Time range arguments (mutually exclusive)
    time_group = parser.add_mutually_exclusive_group(required=True)
    time_group.add_argument(
        "--days",
        type=int,
        help="Number of days to look back from now",
    )
    time_group.add_argument(
        "--start-time",
        help="Start time (ISO format or Unix timestamp)",
    )

    parser.add_argument(
        "--end-time",
        help="End time (ISO format or Unix timestamp, used with --start-time)",
    )

    # Export format
    parser.add_argument(
        "--format",
        choices=["csv", "parquet", "both"],
        default="both",
        help="Export format (default: both)",
    )

    # Output directory
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports"),
        help="Output directory (default: exports/)",
    )

    # Database selection
    parser.add_argument(
        "--database",
        choices=["production", "training"],
        default="production",
        help="Database to export from (default: production)",
    )

    args = parser.parse_args()

    # Validate end_time usage
    if args.end_time and not args.start_time:
        parser.error("--end-time requires --start-time")

    # Parse time range
    try:
        start_time, end_time = parse_time_range(
            days=args.days,
            start_time=args.start_time,
            end_time=args.end_time,
        )
    except ValueError as e:
        parser.error(str(e))

    # Parse export formats
    export_formats = ["csv", "parquet"] if args.format == "both" else [args.format]

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Select database URL based on argument
    db_url = (
        settings.training_database_url_str
        if args.database == "training"
        else settings.database_url_str
    )

    # Create database engine and session
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Resolve starlisting parameters from database
        try:
            args.exchange, args.quote, args.market_type = await get_starlisting_params(
                session=session,
                coin=args.coin,
                exchange=args.exchange,
                quote=args.quote,
                market_type=args.market_type,
            )
        except ValueError as e:
            print(f"ERROR: {e}")
            return 1

        # Get available intervals
        available_intervals = await get_available_intervals(session)

        # Parse intervals
        try:
            intervals_to_export = parse_intervals(args.intervals, available_intervals)
        except ValueError as e:
            print(f"ERROR: {e}")
            return 1

        print(f"{'='*60}")
        print(f"Kirby Candle Data Export")
        print(f"{'='*60}")
        print(f"Database: {args.database}")
        print(f"Coin: {args.coin}")
        print(f"Exchange: {args.exchange}")
        print(f"Quote: {args.quote}")
        print(f"Market Type: {args.market_type}")
        print(f"Intervals: {', '.join(intervals_to_export)}")
        print(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}")
        print(f"Formats: {', '.join(export_formats)}")
        print(f"Output: {args.output.absolute()}")
        print(f"{'='*60}\n")

        # Export data for each interval
        success_count = 0
        for interval in intervals_to_export:
            success = await export_candles_for_interval(
                session,
                args.exchange,
                args.coin,
                args.quote,
                args.market_type,
                interval,
                start_time,
                end_time,
                args.output,
                export_formats,
            )
            if success:
                success_count += 1

        print(f"\n{'='*60}")
        print(f"Export Complete: {success_count}/{len(intervals_to_export)} intervals exported successfully")
        print(f"{'='*60}\n")

    await engine.dispose()

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
