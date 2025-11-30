"""
Export merged dataset with candles + funding + open interest aligned by timestamp.

This script creates ML-ready datasets by merging OHLCV candles with funding rates
and open interest data, all aligned by minute-precision timestamps.

Usage:
    python -m scripts.export_all --coin BTC --intervals 1m --days 30
    python -m scripts.export_all --coin BTC --intervals all --days 90 --format parquet
    python -m scripts.export_all --coin SOL --intervals 1m,15m --start-time 2025-10-01 --end-time 2025-11-01
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
from src.db.models import (
    Candle,
    Coin,
    Exchange,
    FundingRate,
    Interval,
    MarketType,
    OpenInterest,
    QuoteCurrency,
    Starlisting,
)
from src.utils.database_helpers import get_starlisting_params
from src.utils.export import (
    export_to_csv,
    export_to_parquet,
    generate_filename,
    generate_metadata,
    parse_intervals,
    parse_time_range,
    print_export_summary,
    save_metadata,
)


async def get_starlisting_id(
    session: AsyncSession,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str,
) -> tuple[int, int] | None:
    """Get starlisting ID and trading_pair_id for specified parameters.

    Returns:
        Tuple of (starlisting_id, trading_pair_id) or None if not found.
    """
    stmt = (
        select(Starlisting.id, Starlisting.trading_pair_id)
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
    row = result.one_or_none()
    return (row[0], row[1]) if row else None


async def export_merged_data_for_interval(
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
    Export merged dataset for a single interval.

    Merges candles + funding + OI aligned by timestamp.
    Missing values are left as NULL (no forward-filling).
    """
    print(f"\nExporting merged {coin} {interval} dataset...")

    # Get starlisting ID for candles and trading_pair_id for funding/OI
    result = await get_starlisting_id(
        session, exchange, coin, quote, market_type, interval
    )

    if not result:
        print(
            f"  ERROR: Starlisting not found for {exchange}/{coin}/{quote}/{market_type}/{interval}"
        )
        return False

    starlisting_id, trading_pair_id = result

    # Query candles (base dataset)
    print(f"  Querying candles...")
    candles_stmt = (
        select(Candle)
        .where(
            Candle.starlisting_id == starlisting_id,
            Candle.time >= start_time,
            Candle.time <= end_time,
        )
        .order_by(Candle.time)
    )

    result = await session.execute(candles_stmt)
    candles = result.scalars().all()

    if not candles:
        print(f"  WARNING: No candle data found for {interval} in specified time range")
        return False

    # Convert candles to DataFrame
    candles_df = pd.DataFrame(
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

    print(f"  Found {len(candles_df):,} candles")

    # Query funding rates (funding is per trading_pair, not per starlisting/interval)
    print(f"  Querying funding rates...")
    funding_stmt = (
        select(FundingRate)
        .where(
            FundingRate.trading_pair_id == trading_pair_id,
            FundingRate.time >= start_time,
            FundingRate.time <= end_time,
        )
        .order_by(FundingRate.time)
    )

    result = await session.execute(funding_stmt)
    funding_rates = result.scalars().all()

    # Convert funding rates to DataFrame
    if funding_rates:
        funding_df = pd.DataFrame(
            [
                {
                    "time": rate.time,
                    "funding_rate": (
                        float(rate.funding_rate) if rate.funding_rate else None
                    ),
                    "premium": float(rate.premium) if rate.premium else None,
                    "mark_price": float(rate.mark_price) if rate.mark_price else None,
                    "index_price": (
                        float(rate.index_price) if rate.index_price else None
                    ),
                    "oracle_price": (
                        float(rate.oracle_price) if rate.oracle_price else None
                    ),
                    "mid_price": float(rate.mid_price) if rate.mid_price else None,
                    "next_funding_time": rate.next_funding_time,
                }
                for rate in funding_rates
            ]
        )
        print(f"  Found {len(funding_df):,} funding rate snapshots")
    else:
        funding_df = pd.DataFrame()
        print(f"  No funding rate data found")

    # Query open interest (OI is per trading_pair, not per starlisting/interval)
    print(f"  Querying open interest...")
    oi_stmt = (
        select(OpenInterest)
        .where(
            OpenInterest.trading_pair_id == trading_pair_id,
            OpenInterest.time >= start_time,
            OpenInterest.time <= end_time,
        )
        .order_by(OpenInterest.time)
    )

    result = await session.execute(oi_stmt)
    oi_records = result.scalars().all()

    # Convert OI to DataFrame
    if oi_records:
        oi_df = pd.DataFrame(
            [
                {
                    "time": record.time,
                    "open_interest": (
                        float(record.open_interest) if record.open_interest else None
                    ),
                    "notional_value": (
                        float(record.notional_value) if record.notional_value else None
                    ),
                    "day_base_volume": (
                        float(record.day_base_volume)
                        if record.day_base_volume
                        else None
                    ),
                    "day_notional_volume": (
                        float(record.day_notional_volume)
                        if record.day_notional_volume
                        else None
                    ),
                }
                for record in oi_records
            ]
        )
        print(f"  Found {len(oi_df):,} open interest snapshots")
    else:
        oi_df = pd.DataFrame()
        print(f"  No open interest data found")

    # Merge all datasets on timestamp (LEFT JOIN from candles)
    print(f"  Merging datasets...")
    merged_df = candles_df

    if not funding_df.empty:
        merged_df = merged_df.merge(funding_df, on="time", how="left")

    if not oi_df.empty:
        merged_df = merged_df.merge(oi_df, on="time", how="left")

    print(
        f"  Merged dataset: {len(merged_df):,} rows, {len(merged_df.columns)} columns"
    )

    # Export timestamp for consistent filenames
    export_timestamp = datetime.now()

    # Export to CSV if requested
    csv_path = None
    if "csv" in export_formats:
        csv_filename = generate_filename(
            "merged",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            "csv",
            export_timestamp,
        )
        csv_path = output_dir / csv_filename
        csv_size = export_to_csv(merged_df, csv_path)
        print(f"  Exported CSV: {csv_filename} ({csv_size / 1024 / 1024:.2f} MB)")

        # Save metadata
        metadata = generate_metadata(
            "merged",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            merged_df["time"].min(),
            merged_df["time"].max(),
            len(merged_df),
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
            "merged",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            "parquet",
            export_timestamp,
        )
        parquet_path = output_dir / parquet_filename
        parquet_size = export_to_parquet(merged_df, parquet_path)
        print(
            f"  Exported Parquet: {parquet_filename} ({parquet_size / 1024 / 1024:.2f} MB)"
        )

        # Save metadata
        metadata = generate_metadata(
            "merged",
            exchange,
            coin,
            quote,
            market_type,
            interval,
            merged_df["time"].min(),
            merged_df["time"].max(),
            len(merged_df),
            parquet_size,
            "parquet",
            export_timestamp,
        )
        metadata_path = parquet_path.with_suffix(".json")
        save_metadata(metadata, metadata_path)

    # Print summary
    print_export_summary(
        "merged",
        coin,
        interval,
        len(merged_df),
        csv_path,
        parquet_path,
        merged_df["time"].min(),
        merged_df["time"].max(),
    )

    return True


async def get_available_intervals(session: AsyncSession) -> list[str]:
    """Get list of all available intervals."""
    stmt = select(Interval.name).order_by(Interval.seconds)
    result = await session.execute(stmt)
    intervals = result.scalars().all()
    return list(intervals)


async def main():
    """Main entry point for merged data export."""
    parser = argparse.ArgumentParser(
        description="Export merged dataset with candles + funding + open interest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export BTC 1m merged dataset for last 30 days (both formats)
  python -m scripts.export_all --coin BTC --intervals 1m --days 30

  # Export SOL all intervals for last 90 days as Parquet only
  python -m scripts.export_all --coin SOL --intervals all --days 90 --format parquet

  # Export BTC specific intervals for custom date range
  python -m scripts.export_all --coin BTC --intervals 1m,15m,4h \\
      --start-time 2025-10-01 --end-time 2025-11-01

  # Export to custom directory
  python -m scripts.export_all --coin BTC --intervals 1m --days 7 \\
      --output /path/to/exports

Note: Missing values in funding/OI data are left as NULL (no forward-filling).
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
        print(f"Kirby Merged Data Export")
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
        print(f"Merge Strategy: LEFT JOIN from candles (missing values = NULL)")
        print(f"{'='*60}\n")

        # Export data for each interval
        success_count = 0
        for interval in intervals_to_export:
            success = await export_merged_data_for_interval(
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
        print(
            f"Export Complete: {success_count}/{len(intervals_to_export)} intervals exported successfully"
        )
        print(f"{'='*60}\n")

    await engine.dispose()

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
