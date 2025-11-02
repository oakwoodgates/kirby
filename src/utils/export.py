"""
Utility functions for data export operations.

This module provides shared functionality for exporting market data to CSV and Parquet formats.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd


def generate_filename(
    data_type: str,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str | None,
    format: Literal["csv", "parquet"],
    timestamp: datetime | None = None,
) -> str:
    """
    Generate a consistent filename for export files.

    Args:
        data_type: Type of data (candles, funding, open_interest, merged)
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type
        interval: Time interval (None for funding/OI which are interval-independent)
        format: File format (csv or parquet)
        timestamp: Timestamp for filename (defaults to now)

    Returns:
        Filename string in the format:
        {data_type}_{exchange}_{coin}_{quote}_{market_type}[_{interval}]_{timestamp}.{format}

    Example:
        >>> generate_filename("candles", "hyperliquid", "BTC", "USD", "perps", "1m", "csv")
        'candles_hyperliquid_BTC_USD_perps_1m_20251102_143022.csv'
    """
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

    if interval:
        filename = f"{data_type}_{exchange}_{coin}_{quote}_{market_type}_{interval}_{timestamp_str}.{format}"
    else:
        filename = f"{data_type}_{exchange}_{coin}_{quote}_{market_type}_{timestamp_str}.{format}"

    return filename


def generate_metadata(
    data_type: str,
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str | None,
    start_time: datetime,
    end_time: datetime,
    row_count: int,
    file_size: int,
    format: Literal["csv", "parquet"],
    export_timestamp: datetime | None = None,
) -> dict[str, Any]:
    """
    Generate metadata dictionary for export.

    Args:
        data_type: Type of data exported
        exchange: Exchange name
        coin: Coin symbol
        quote: Quote currency symbol
        market_type: Market type
        interval: Time interval (None for funding/OI)
        start_time: Start time of data range
        end_time: End time of data range
        row_count: Number of rows exported
        file_size: File size in bytes
        format: Export format
        export_timestamp: Time of export (defaults to now)

    Returns:
        Dictionary with export metadata
    """
    if export_timestamp is None:
        export_timestamp = datetime.now()

    metadata = {
        "export_timestamp": export_timestamp.isoformat(),
        "data_type": data_type,
        "exchange": exchange,
        "coin": coin,
        "quote": quote,
        "trading_pair": f"{coin}/{quote}",
        "market_type": market_type,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "row_count": row_count,
        "file_size_bytes": file_size,
        "format": format,
        "null_strategy": "preserve",
    }

    if interval:
        metadata["interval"] = interval

    return metadata


def save_metadata(metadata: dict[str, Any], metadata_path: Path | str) -> None:
    """
    Save metadata to JSON file.

    Args:
        metadata: Metadata dictionary
        metadata_path: Path to save metadata file
    """
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def export_to_csv(df: pd.DataFrame, output_path: Path | str) -> int:
    """
    Export DataFrame to CSV file.

    Args:
        df: DataFrame to export
        output_path: Path to save CSV file

    Returns:
        File size in bytes
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)

    return os.path.getsize(output_path)


def export_to_parquet(df: pd.DataFrame, output_path: Path | str) -> int:
    """
    Export DataFrame to Parquet file.

    Args:
        df: DataFrame to export
        output_path: Path to save Parquet file

    Returns:
        File size in bytes
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(output_path, index=False, engine="pyarrow", compression="snappy")

    return os.path.getsize(output_path)


def parse_time_range(
    days: int | None = None,
    start_time: str | datetime | None = None,
    end_time: str | datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Parse time range arguments into start and end datetime objects.

    Args:
        days: Number of days to look back from now (mutually exclusive with start/end)
        start_time: Start time (ISO format string, Unix timestamp, or datetime)
        end_time: End time (ISO format string, Unix timestamp, or datetime)

    Returns:
        Tuple of (start_time, end_time) as datetime objects

    Raises:
        ValueError: If both days and start/end are provided, or if neither is provided
    """
    if days is not None and (start_time is not None or end_time is not None):
        raise ValueError("Cannot specify both 'days' and 'start_time/end_time'")

    if days is None and start_time is None and end_time is None:
        raise ValueError("Must specify either 'days' or 'start_time/end_time'")

    now = datetime.now()

    if days is not None:
        # Use last N days
        end = now
        start = now - timedelta(days=days)
        return start, end

    # Parse start_time
    if start_time is None:
        start = datetime.min
    elif isinstance(start_time, datetime):
        start = start_time
    elif isinstance(start_time, str):
        try:
            # Try parsing as ISO format
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            # Try parsing as Unix timestamp
            try:
                start = datetime.fromtimestamp(float(start_time))
            except ValueError:
                raise ValueError(
                    f"Invalid start_time format: {start_time}. Use ISO format or Unix timestamp."
                )
    else:
        raise ValueError(f"Invalid start_time type: {type(start_time)}")

    # Parse end_time
    if end_time is None:
        end = now
    elif isinstance(end_time, datetime):
        end = end_time
    elif isinstance(end_time, str):
        try:
            # Try parsing as ISO format
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            # Try parsing as Unix timestamp
            try:
                end = datetime.fromtimestamp(float(end_time))
            except ValueError:
                raise ValueError(
                    f"Invalid end_time format: {end_time}. Use ISO format or Unix timestamp."
                )
    else:
        raise ValueError(f"Invalid end_time type: {type(end_time)}")

    return start, end


def print_export_summary(
    data_type: str,
    coin: str,
    interval: str | None,
    row_count: int,
    csv_path: Path | None,
    parquet_path: Path | None,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """
    Print a summary of the export operation.

    Args:
        data_type: Type of data exported
        coin: Coin symbol
        interval: Time interval (None for funding/OI)
        row_count: Number of rows exported
        csv_path: Path to CSV file (None if not exported)
        parquet_path: Path to Parquet file (None if not exported)
        start_time: Start time of data range
        end_time: End time of data range
    """
    interval_str = f" ({interval})" if interval else ""
    print(f"\n{'='*60}")
    print(f"Export Summary: {data_type.upper()} - {coin}{interval_str}")
    print(f"{'='*60}")
    print(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}")
    print(f"Records Exported: {row_count:,}")

    if csv_path:
        csv_size_mb = os.path.getsize(csv_path) / 1024 / 1024
        print(f"CSV File: {csv_path.name} ({csv_size_mb:.2f} MB)")

    if parquet_path:
        parquet_size_mb = os.path.getsize(parquet_path) / 1024 / 1024
        print(f"Parquet File: {parquet_path.name} ({parquet_size_mb:.2f} MB)")

        if csv_path:
            csv_size = os.path.getsize(csv_path)
            parquet_size = os.path.getsize(parquet_path)
            compression_ratio = (1 - parquet_size / csv_size) * 100
            print(f"Compression: Parquet is {compression_ratio:.1f}% smaller than CSV")

    print(f"{'='*60}\n")


def parse_intervals(intervals_str: str, available_intervals: list[str]) -> list[str]:
    """
    Parse interval string into list of intervals.

    Args:
        intervals_str: Comma-separated interval string or "all"
        available_intervals: List of available intervals

    Returns:
        List of interval names

    Example:
        >>> parse_intervals("1m,15m,4h", ["1m", "15m", "4h", "1d"])
        ['1m', '15m', '4h']
        >>> parse_intervals("all", ["1m", "15m", "4h", "1d"])
        ['1m', '15m', '4h', '1d']
    """
    if intervals_str.lower() == "all":
        return available_intervals

    intervals = [i.strip() for i in intervals_str.split(",")]

    # Validate intervals
    invalid = [i for i in intervals if i not in available_intervals]
    if invalid:
        raise ValueError(
            f"Invalid intervals: {invalid}. Available: {available_intervals}"
        )

    return intervals
