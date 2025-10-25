"""
Centralized interval configuration and management.

Provides utilities for:
- Validating candle intervals
- Getting interval metadata (duration, frequency, batch sizes)
- Converting between formats (Kirby interval ↔ CCXT timeframe)
- Calculating optimal collection/backfill parameters
"""

from typing import Dict, List


class IntervalManager:
    """
    Centralized manager for candle interval configuration.

    Single source of truth for:
    - Supported intervals
    - Interval metadata (duration, optimal frequencies)
    - Conversion utilities
    """

    # Supported candle intervals (matches database validation)
    SUPPORTED_INTERVALS = [
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "8h", "12h",
        "1d", "3d", "1w"
    ]

    # Interval specifications with metadata for each
    INTERVAL_SPECS: Dict[str, Dict] = {
        "1m": {
            "seconds": 60,
            "ccxt_timeframe": "1m",
            "candles_per_day": 1440,
            "display_name": "1 Minute",
        },
        "3m": {
            "seconds": 180,
            "ccxt_timeframe": "3m",
            "candles_per_day": 480,
            "display_name": "3 Minutes",
        },
        "5m": {
            "seconds": 300,
            "ccxt_timeframe": "5m",
            "candles_per_day": 288,
            "display_name": "5 Minutes",
        },
        "15m": {
            "seconds": 900,
            "ccxt_timeframe": "15m",
            "candles_per_day": 96,
            "display_name": "15 Minutes",
        },
        "30m": {
            "seconds": 1800,
            "ccxt_timeframe": "30m",
            "candles_per_day": 48,
            "display_name": "30 Minutes",
        },
        "1h": {
            "seconds": 3600,
            "ccxt_timeframe": "1h",
            "candles_per_day": 24,
            "display_name": "1 Hour",
        },
        "2h": {
            "seconds": 7200,
            "ccxt_timeframe": "2h",
            "candles_per_day": 12,
            "display_name": "2 Hours",
        },
        "4h": {
            "seconds": 14400,
            "ccxt_timeframe": "4h",
            "candles_per_day": 6,
            "display_name": "4 Hours",
        },
        "8h": {
            "seconds": 28800,
            "ccxt_timeframe": "8h",
            "candles_per_day": 3,
            "display_name": "8 Hours",
        },
        "12h": {
            "seconds": 43200,
            "ccxt_timeframe": "12h",
            "candles_per_day": 2,
            "display_name": "12 Hours",
        },
        "1d": {
            "seconds": 86400,
            "ccxt_timeframe": "1d",
            "candles_per_day": 1,
            "display_name": "1 Day",
        },
        "3d": {
            "seconds": 259200,
            "ccxt_timeframe": "3d",
            "candles_per_day": 0.333,
            "display_name": "3 Days",
        },
        "1w": {
            "seconds": 604800,
            "ccxt_timeframe": "1w",
            "candles_per_day": 0.143,
            "display_name": "1 Week",
        },
    }

    @classmethod
    def validate_intervals(cls, intervals: List[str]) -> List[str]:
        """
        Validate and normalize a list of intervals.

        Args:
            intervals: List of interval strings to validate

        Returns:
            Validated intervals sorted by duration (shortest first)

        Raises:
            ValueError: If any intervals are invalid
        """
        if not intervals:
            raise ValueError("At least one interval must be specified")

        invalid = [i for i in intervals if i not in cls.SUPPORTED_INTERVALS]
        if invalid:
            raise ValueError(
                f"Invalid intervals: {invalid}. "
                f"Supported intervals: {cls.SUPPORTED_INTERVALS}"
            )

        # Remove duplicates and sort by duration
        unique_intervals = list(set(intervals))
        return sorted(unique_intervals, key=lambda x: cls.INTERVAL_SPECS[x]["seconds"])

    @classmethod
    def get_interval_duration(cls, interval: str) -> int:
        """
        Get the duration of an interval in seconds.

        Args:
            interval: Interval string (e.g., "1m", "4h")

        Returns:
            Duration in seconds

        Raises:
            ValueError: If interval is not supported
        """
        if interval not in cls.INTERVAL_SPECS:
            raise ValueError(f"Unsupported interval: {interval}")
        return cls.INTERVAL_SPECS[interval]["seconds"]

    @classmethod
    def get_ccxt_timeframe(cls, interval: str) -> str:
        """
        Convert Kirby interval to CCXT timeframe format.

        Args:
            interval: Kirby interval (e.g., "1m", "4h")

        Returns:
            CCXT timeframe string

        Raises:
            ValueError: If interval is not supported
        """
        if interval not in cls.INTERVAL_SPECS:
            raise ValueError(f"Unsupported interval: {interval}")
        return cls.INTERVAL_SPECS[interval]["ccxt_timeframe"]

    @classmethod
    def get_poll_frequency(cls, interval: str) -> int:
        """
        Get optimal polling frequency for an interval.

        Polls at 50% of interval duration (minimum 10 seconds) to ensure
        we catch new candles without excessive API calls.

        Examples:
            1m → poll every 30s
            15m → poll every 7.5 min (450s)
            4h → poll every 2 hours (7200s)
            1d → poll every 12 hours (43200s)

        Args:
            interval: Candle interval

        Returns:
            Polling frequency in seconds

        Raises:
            ValueError: If interval is not supported
        """
        duration = cls.get_interval_duration(interval)
        # Poll at 50% of interval, minimum 10 seconds
        return max(duration // 2, 10)

    @classmethod
    def get_backfill_batch_size(cls, interval: str) -> int:
        """
        Get optimal batch size for backfilling an interval.

        Targets fetching ~1 week of data per batch (max 1000 candles).
        Shorter intervals use smaller batches to avoid rate limits.

        Examples:
            1m → 500 candles (~8 hours)
            15m → 672 candles (1 week)
            4h → 42 candles (1 week)
            1d → 7 candles (1 week)

        Args:
            interval: Candle interval

        Returns:
            Batch size (number of candles)

        Raises:
            ValueError: If interval is not supported
        """
        if interval not in cls.INTERVAL_SPECS:
            raise ValueError(f"Unsupported interval: {interval}")

        candles_per_day = cls.INTERVAL_SPECS[interval]["candles_per_day"]

        # Target 1 week of data, capped at 1000
        one_week = int(candles_per_day * 7)

        # For very high-frequency (1m, 3m, 5m), use smaller batches
        if candles_per_day >= 288:  # 5m or shorter
            return min(500, one_week)

        return min(1000, one_week)

    @classmethod
    def get_interval_info(cls, interval: str) -> Dict:
        """
        Get complete metadata for an interval.

        Args:
            interval: Candle interval

        Returns:
            Dictionary with all interval metadata

        Raises:
            ValueError: If interval is not supported
        """
        if interval not in cls.INTERVAL_SPECS:
            raise ValueError(f"Unsupported interval: {interval}")

        spec = cls.INTERVAL_SPECS[interval].copy()
        spec["interval"] = interval
        spec["poll_frequency_seconds"] = cls.get_poll_frequency(interval)
        spec["backfill_batch_size"] = cls.get_backfill_batch_size(interval)

        return spec

    @classmethod
    def format_interval_list(cls, intervals: List[str]) -> str:
        """
        Format list of intervals for logging/display.

        Args:
            intervals: List of intervals

        Returns:
            Formatted string (e.g., "1m, 15m, 4h, 1d")
        """
        return ", ".join(sorted(intervals, key=lambda x: cls.get_interval_duration(x)))
