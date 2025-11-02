"""
Helper utilities for Kirby.
"""
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def timestamp_to_datetime(ts: int | float) -> datetime:
    """
    Convert Unix timestamp (seconds or milliseconds) to datetime.

    Args:
        ts: Unix timestamp in seconds or milliseconds

    Returns:
        Timezone-aware datetime object
    """
    # Auto-detect milliseconds vs seconds
    if ts > 1e10:  # Likely milliseconds
        ts = ts / 1000.0

    return datetime.fromtimestamp(ts, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime to Unix timestamp in milliseconds.

    Args:
        dt: Datetime object

    Returns:
        Unix timestamp in milliseconds
    """
    return int(dt.timestamp() * 1000)


def truncate_to_minute(dt: datetime) -> datetime:
    """
    Truncate datetime to minute precision (remove seconds and microseconds).

    This is used to align funding/OI data timestamps with candle data timestamps.
    Candle timestamps represent the START of the minute interval.

    Args:
        dt: Datetime object with any precision

    Returns:
        Datetime truncated to minute (seconds and microseconds set to 0)

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2025, 11, 2, 13, 58, 32, 586045, tzinfo=timezone.utc)
        >>> truncate_to_minute(dt)
        datetime.datetime(2025, 11, 2, 13, 58, 0, tzinfo=datetime.timezone.utc)
    """
    return dt.replace(second=0, microsecond=0)


def normalize_candle_data(
    raw_candle: dict[str, Any],
    source: str = "unknown",
) -> dict[str, Any]:
    """
    Normalize candle data from various exchange formats to Kirby format.

    Args:
        raw_candle: Raw candle data from exchange
        source: Source exchange name

    Returns:
        Normalized candle dict with keys:
            time, open, high, low, close, volume, num_trades
    """
    if source == "hyperliquid":
        # Hyperliquid format: {t, T, s, i, o, c, h, l, v, n}
        return {
            "time": timestamp_to_datetime(raw_candle["t"]),
            "open": float(raw_candle["o"]),
            "high": float(raw_candle["h"]),
            "low": float(raw_candle["l"]),
            "close": float(raw_candle["c"]),
            "volume": float(raw_candle.get("v", 0)),
            "num_trades": raw_candle.get("n"),
        }
    elif source == "ccxt":
        # CCXT format: [timestamp, open, high, low, close, volume]
        return {
            "time": timestamp_to_datetime(raw_candle[0]),
            "open": float(raw_candle[1]),
            "high": float(raw_candle[2]),
            "low": float(raw_candle[3]),
            "close": float(raw_candle[4]),
            "volume": float(raw_candle[5]) if raw_candle[5] else 0,
            "num_trades": None,
        }
    else:
        raise ValueError(f"Unknown candle source: {source}")


def validate_candle(candle: dict[str, Any]) -> bool:
    """
    Validate candle data for basic consistency.

    Args:
        candle: Candle dictionary

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required fields
        required = ["time", "open", "high", "low", "close", "volume"]
        if not all(key in candle for key in required):
            return False

        # Type validation
        if not isinstance(candle["time"], datetime):
            return False

        # Convert to float for validation
        o = float(candle["open"])
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])
        v = float(candle["volume"])

        # Basic consistency checks
        if h < l:  # High must be >= low
            return False
        if h < o or h < c:  # High must be >= open and close
            return False
        if l > o or l > c:  # Low must be <= open and close
            return False
        if o <= 0 or h <= 0 or l <= 0 or c <= 0:  # Prices must be positive
            return False
        if v < 0:  # Volume must be non-negative
            return False

        return True

    except (ValueError, TypeError, KeyError):
        return False


def interval_to_seconds(interval: str) -> int:
    """
    Convert interval string to seconds.

    Args:
        interval: Interval string (e.g., '1m', '15m', '4h', '1d')

    Returns:
        Number of seconds

    Raises:
        ValueError: If interval format is invalid
    """
    units = {
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }

    if not interval or len(interval) < 2:
        raise ValueError(f"Invalid interval format: {interval}")

    # Extract number and unit
    number = interval[:-1]
    unit = interval[-1]

    if unit not in units:
        raise ValueError(f"Invalid interval unit: {unit}")

    try:
        return int(number) * units[unit]
    except ValueError:
        raise ValueError(f"Invalid interval number: {number}")
