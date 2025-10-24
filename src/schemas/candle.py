"""
Pydantic schemas for Candle data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CandleSchema(BaseModel):
    """Base candle schema for validation."""

    listing_id: int = Field(..., gt=0, description="Listing ID")
    timestamp: datetime = Field(..., description="Candle timestamp")
    interval: str = Field(..., description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)")
    open: Decimal = Field(..., gt=0, description="Opening price")
    high: Decimal = Field(..., gt=0, description="Highest price")
    low: Decimal = Field(..., gt=0, description="Lowest price")
    close: Decimal = Field(..., gt=0, description="Closing price")
    volume: Decimal = Field(..., ge=0, description="Trading volume")
    trades_count: Optional[int] = Field(None, ge=0, description="Number of trades")

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Validate candle interval."""
        valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"]
        if v not in valid_intervals:
            raise ValueError(f"Invalid interval: {v}. Must be one of {valid_intervals}")
        return v

    @model_validator(mode='after')
    def validate_ohlc_integrity(self) -> 'CandleSchema':
        """
        Validate OHLC price relationships after all fields are populated.

        Ensures candle data integrity:
        - high >= max(open, close) - High must be at or above opening/closing price
        - low <= min(open, close) - Low must be at or below opening/closing price
        - high >= low - High cannot be below low

        This model-level validator runs after all fields are populated, ensuring
        reliable validation regardless of field order.
        """
        # Check high >= max(open, close)
        max_price = max(self.open, self.close)
        if self.high < max_price:
            raise ValueError(
                f"Invalid candle: high ({self.high}) must be >= max(open={self.open}, close={self.close})"
            )

        # Check low <= min(open, close)
        min_price = min(self.open, self.close)
        if self.low > min_price:
            raise ValueError(
                f"Invalid candle: low ({self.low}) must be <= min(open={self.open}, close={self.close})"
            )

        # Check high >= low
        if self.high < self.low:
            raise ValueError(
                f"Invalid candle: high ({self.high}) cannot be less than low ({self.low})"
            )

        return self

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "listing_id": 1,
                "timestamp": "2025-01-23T12:00:00Z",
                "interval": "1m",
                "open": "50000.00",
                "high": "50100.00",
                "low": "49900.00",
                "close": "50050.00",
                "volume": "125.5",
                "trades_count": 1542,
            }
        },
    }


class CandleCreate(CandleSchema):
    """Schema for creating a candle (same as base)."""

    pass


class CandleResponse(CandleSchema):
    """Schema for candle API response."""

    created_at: datetime = Field(..., description="When this record was created")

    model_config = {
        "from_attributes": True,
    }
