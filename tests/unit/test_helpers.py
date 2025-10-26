"""
Unit tests for utility helper functions.
"""
from datetime import datetime, timezone

import pytest

from src.utils.helpers import (
    datetime_to_timestamp,
    interval_to_seconds,
    normalize_candle_data,
    timestamp_to_datetime,
    utc_now,
    validate_candle,
)


class TestTimestampConversion:
    """Test timestamp conversion utilities."""

    def test_utc_now_returns_aware_datetime(self):
        """Test that utc_now returns timezone-aware datetime."""
        now = utc_now()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_timestamp_to_datetime_seconds(self):
        """Test conversion from Unix timestamp in seconds."""
        ts = 1609459200  # 2021-01-01 00:00:00 UTC
        dt = timestamp_to_datetime(ts)
        assert dt.year == 2021
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.tzinfo == timezone.utc

    def test_timestamp_to_datetime_milliseconds(self):
        """Test conversion from Unix timestamp in milliseconds."""
        ts = 1609459200000  # 2021-01-01 00:00:00 UTC
        dt = timestamp_to_datetime(ts)
        assert dt.year == 2021
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.tzinfo == timezone.utc

    def test_datetime_to_timestamp(self):
        """Test conversion from datetime to millisecond timestamp."""
        dt = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        ts = datetime_to_timestamp(dt)
        assert ts == 1609459200000

    def test_timestamp_roundtrip(self):
        """Test roundtrip conversion maintains timestamp."""
        original_ts = 1609459200000
        dt = timestamp_to_datetime(original_ts)
        result_ts = datetime_to_timestamp(dt)
        assert result_ts == original_ts


class TestNormalizeCandleData:
    """Test candle data normalization from various sources."""

    def test_normalize_hyperliquid_candle(self):
        """Test normalization of Hyperliquid candle format."""
        raw = {
            "t": 1609459200000,
            "o": "40000.5",
            "h": "40500.0",
            "l": "39800.0",
            "c": "40200.0",
            "v": "1234.56",
            "n": 42,
        }
        result = normalize_candle_data(raw, source="hyperliquid")

        assert isinstance(result["time"], datetime)
        assert result["open"] == 40000.5
        assert result["high"] == 40500.0
        assert result["low"] == 39800.0
        assert result["close"] == 40200.0
        assert result["volume"] == 1234.56
        assert result["num_trades"] == 42

    def test_normalize_hyperliquid_candle_missing_volume(self):
        """Test normalization handles missing volume."""
        raw = {
            "t": 1609459200000,
            "o": "40000.5",
            "h": "40500.0",
            "l": "39800.0",
            "c": "40200.0",
        }
        result = normalize_candle_data(raw, source="hyperliquid")
        assert result["volume"] == 0

    def test_normalize_ccxt_candle(self):
        """Test normalization of CCXT candle format."""
        raw = [1609459200000, 40000.5, 40500.0, 39800.0, 40200.0, 1234.56]
        result = normalize_candle_data(raw, source="ccxt")

        assert isinstance(result["time"], datetime)
        assert result["open"] == 40000.5
        assert result["high"] == 40500.0
        assert result["low"] == 39800.0
        assert result["close"] == 40200.0
        assert result["volume"] == 1234.56
        assert result["num_trades"] is None

    def test_normalize_ccxt_candle_null_volume(self):
        """Test normalization handles null volume from CCXT."""
        raw = [1609459200000, 40000.5, 40500.0, 39800.0, 40200.0, None]
        result = normalize_candle_data(raw, source="ccxt")
        assert result["volume"] == 0

    def test_normalize_unknown_source_raises_error(self):
        """Test that unknown source raises ValueError."""
        raw = {"some": "data"}
        with pytest.raises(ValueError, match="Unknown candle source"):
            normalize_candle_data(raw, source="unknown_exchange")


class TestValidateCandle:
    """Test candle data validation."""

    def test_validate_valid_candle(self):
        """Test that valid candle passes validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": 1234.56,
            "num_trades": 42,
        }
        assert validate_candle(candle) is True

    def test_validate_missing_required_field(self):
        """Test that missing required field fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            # Missing volume
        }
        assert validate_candle(candle) is False

    def test_validate_invalid_time_type(self):
        """Test that non-datetime time fails validation."""
        candle = {
            "time": "2021-01-01",  # String instead of datetime
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": 1234.56,
        }
        assert validate_candle(candle) is False

    def test_validate_high_less_than_low(self):
        """Test that high < low fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 39800.0,  # High less than low
            "low": 40500.0,
            "close": 40200.0,
            "volume": 1234.56,
        }
        assert validate_candle(candle) is False

    def test_validate_high_less_than_open(self):
        """Test that high < open fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40500.0,
            "high": 40000.0,  # High less than open
            "low": 39800.0,
            "close": 40200.0,
            "volume": 1234.56,
        }
        assert validate_candle(candle) is False

    def test_validate_low_greater_than_close(self):
        """Test that low > close fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 40500.0,
            "low": 40300.0,  # Low greater than close
            "close": 40200.0,
            "volume": 1234.56,
        }
        assert validate_candle(candle) is False

    def test_validate_negative_price(self):
        """Test that negative price fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": -40000.0,  # Negative price
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": 1234.56,
        }
        assert validate_candle(candle) is False

    def test_validate_negative_volume(self):
        """Test that negative volume fails validation."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": -1234.56,  # Negative volume
        }
        assert validate_candle(candle) is False

    def test_validate_zero_volume(self):
        """Test that zero volume is valid."""
        candle = {
            "time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": 0,  # Zero is valid
        }
        assert validate_candle(candle) is True


class TestIntervalToSeconds:
    """Test interval string to seconds conversion."""

    def test_interval_minutes(self):
        """Test conversion of minute intervals."""
        assert interval_to_seconds("1m") == 60
        assert interval_to_seconds("5m") == 300
        assert interval_to_seconds("15m") == 900

    def test_interval_hours(self):
        """Test conversion of hour intervals."""
        assert interval_to_seconds("1h") == 3600
        assert interval_to_seconds("4h") == 14400
        assert interval_to_seconds("24h") == 86400

    def test_interval_days(self):
        """Test conversion of day intervals."""
        assert interval_to_seconds("1d") == 86400
        assert interval_to_seconds("7d") == 604800

    def test_interval_weeks(self):
        """Test conversion of week intervals."""
        assert interval_to_seconds("1w") == 604800
        assert interval_to_seconds("2w") == 1209600

    def test_interval_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid interval format"):
            interval_to_seconds("")

        with pytest.raises(ValueError, match="Invalid interval format"):
            interval_to_seconds("x")

    def test_interval_invalid_unit(self):
        """Test that invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid interval unit"):
            interval_to_seconds("5x")

    def test_interval_invalid_number(self):
        """Test that invalid number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid interval number"):
            interval_to_seconds("abcm")
