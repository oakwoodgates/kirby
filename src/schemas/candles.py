"""
Pydantic schemas for candle-related API endpoints.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CandleResponse(BaseModel):
    """Response model for a single candle."""

    time: datetime = Field(..., description="Candle timestamp (open time)")
    open: Decimal = Field(..., description="Opening price")
    high: Decimal = Field(..., description="Highest price")
    low: Decimal = Field(..., description="Lowest price")
    close: Decimal = Field(..., description="Closing price")
    volume: Decimal = Field(..., description="Trading volume")
    num_trades: int | None = Field(None, description="Number of trades (if available)")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "time": "2025-10-26T12:00:00Z",
                "open": "67500.50",
                "high": "67800.00",
                "low": "67400.25",
                "close": "67650.75",
                "volume": "1234.5678",
                "num_trades": 542,
            }
        }


class CandleMetadata(BaseModel):
    """Metadata for candle list response."""

    exchange: str = Field(..., description="Exchange name")
    coin: str = Field(..., description="Base asset symbol")
    quote: str = Field(..., description="Quote asset symbol")
    trading_pair: str = Field(..., description="Trading pair (e.g., BTC/USD)")
    market_type: str = Field(..., description="Market type")
    interval: str = Field(..., description="Time interval")
    count: int = Field(..., description="Number of candles returned")
    start_time: datetime | None = Field(None, description="Requested start time")
    end_time: datetime | None = Field(None, description="Requested end time")


class CandleListResponse(BaseModel):
    """Response model for list of candles."""

    data: list[CandleResponse] = Field(..., description="List of candles")
    metadata: CandleMetadata = Field(..., description="Query metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "time": "2025-10-26T12:00:00Z",
                        "open": "67500.50",
                        "high": "67800.00",
                        "low": "67400.25",
                        "close": "67650.75",
                        "volume": "1234.5678",
                        "num_trades": 542,
                    }
                ],
                "metadata": {
                    "exchange": "hyperliquid",
                    "coin": "BTC",
                    "quote": "USD",
                    "trading_pair": "BTC/USD",
                    "market_type": "perps",
                    "interval": "15m",
                    "count": 1,
                    "start_time": None,
                    "end_time": None,
                },
            }
        }
