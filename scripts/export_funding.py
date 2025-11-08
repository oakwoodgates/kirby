"""
Export funding rate data to CSV and Parquet formats.

This script exports historical funding rate data for specified trading pairs,
optimized for AI/ML training and backtesting.

Usage:
    python -m scripts.export_funding --coin BTC --days 30
    python -m scripts.export_funding --coin BTC --days 90 --format parquet
    python -m scripts.export_funding --coin SOL --start-time 2025-10-01 --end-time 2025-11-01
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
from src.db.models import Coin, Exchange, MarketType, QuoteCurrency, Starlisting, FundingRate
from src.utils.database_helpers import get_starlisting_params
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

    Note: For funding rates, we just need any starlisting for this trading pair
    since funding rates are the same across all intervals.

    Args:
        session: Database session
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type

    Returns:
        Starlisting ID or None if not found
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
        .limit(1)  # Get any one starlisting for this trading pair
    )

    result = await session.execute(stmt)
    starlisting_id = result.scalar_one_or_none()

    return starlisting_id


async def export_funding_rates(
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
    """
    Export funding rate data.

    Args:
        session: Database session
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type
        start_time: Start time for data
        end_time: End time for data
        output_dir: Output directory
        export_formats: List of formats to export ('csv', 'parquet', or both)

    Returns:
        True if export successful, False otherwise
    """
    print(f"\nExporting {coin} funding rates...")

    # Get starlisting ID
    starlisting_id = await get_starlisting_id(
        session, exchange, coin, quote, market_type
    )

    if not starlisting_id:
        print(f"  ERROR: Trading pair not found for {exchange}/{coin}/{quote}/{market_type}")
        return False

    # Query funding rate data
    stmt = (
        select(FundingRate)
        .where(
            FundingRate.starlisting_id == starlisting_id,
            FundingRate.time >= start_time,
            FundingRate.time <= end_time,
        )
        .order_by(FundingRate.time)
    )

    result = await session.execute(stmt)
    funding_rates = result.scalars().all()

    if not funding_rates:
        print(f"  WARNING: No funding rate data found in specified time range")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(
        [
            {
                "time": rate.time,
                "funding_rate": float(rate.funding_rate) if rate.funding_rate else None,
                "premium": float(rate.premium) if rate.premium else None,
                "mark_price": float(rate.mark_price) if rate.mark_price else None,
                "index_price": float(rate.index_price) if rate.index_price else None,
                "oracle_price": float(rate.oracle_price) if rate.oracle_price else None,
                "mid_price": float(rate.mid_price) if rate.mid_price else None,
                "next_funding_time": rate.next_funding_time,
            }
            for rate in funding_rates
        ]
    )

    print(f"  Found {len(df):,} funding rate snapshots")

    # Export timestamp for consistent filenames
    export_timestamp = datetime.now()

    # Export to CSV if requested
    csv_path = None
    if "csv" in export_formats:
        csv_filename = generate_filename(
            "funding", exchange, coin, quote, market_type, None, "csv", export_timestamp
        )
        csv_path = output_dir / csv_filename
        csv_size = export_to_csv(df, csv_path)
        print(f"  Exported CSV: {csv_filename} ({csv_size / 1024 / 1024:.2f} MB)")

        # Save metadata
        metadata = generate_metadata(
            "funding",
            exchange,
            coin,
            quote,
            market_type,
            None,  # No interval for funding rates
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
            "funding", exchange, coin, quote, market_type, None, "parquet", export_timestamp
        )
        parquet_path = output_dir / parquet_filename
        parquet_size = export_to_parquet(df, parquet_path)
        print(f"  Exported Parquet: {parquet_filename} ({parquet_size / 1024 / 1024:.2f} MB)")

        # Save metadata
        metadata = generate_metadata(
            "funding",
            exchange,
            coin,
            quote,
            market_type,
            None,  # No interval for funding rates
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
        "funding",
        coin,
        None,  # No interval for funding rates
        len(df),
        csv_path,
        parquet_path,
        df["time"].min(),
        df["time"].max(),
    )

    return True


async def main():
    """Main entry point for funding rate export."""
    parser = argparse.ArgumentParser(
        description="Export funding rate data to CSV and Parquet formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export BTC funding rates for last 30 days (both formats)
  python -m scripts.export_funding --coin BTC --days 30

  # Export SOL funding rates for last 90 days as Parquet only
  python -m scripts.export_funding --coin SOL --days 90 --format parquet

  # Export BTC funding rates for custom date range
  python -m scripts.export_funding --coin BTC \\
      --start-time 2025-10-01 --end-time 2025-11-01

  # Export to custom directory
  python -m scripts.export_funding --coin BTC --days 7 \\
      --output /path/to/exports
        """,
    )

    # Required arguments
    parser.add_argument(
        "--coin",
        required=True,
        help="Coin symbol (e.g., BTC, ETH, SOL)",
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

        print(f"{'='*60}")
        print(f"Kirby Funding Rate Data Export")
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

        # Export funding rate data
        success = await export_funding_rates(
            session,
            args.exchange,
            args.coin,
            args.quote,
            args.market_type,
            start_time,
            end_time,
            args.output,
            export_formats,
        )

        if success:
            print(f"\n{'='*60}")
            print(f"Export Complete: Funding rate data exported successfully")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print(f"Export Failed: No data exported")
            print(f"{'='*60}\n")

    await engine.dispose()

    return 0 if success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
