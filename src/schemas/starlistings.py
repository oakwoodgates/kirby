"""
Pydantic schemas for starlisting-related API endpoints.
"""
from pydantic import BaseModel, ConfigDict, Field


class StarlistingResponse(BaseModel):
    """Response model for a starlisting."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "exchange": "hyperliquid",
                "exchange_display": "Hyperliquid",
                "coin": "BTC",
                "coin_name": "Bitcoin",
                "quote": "USD",
                "quote_name": "US Dollar",
                "trading_pair": "BTC/USD",
                "market_type": "perps",
                "market_type_display": "Perpetuals",
                "interval": "15m",
                "interval_seconds": 900,
                "active": True,
            }
        }
    )

    id: int = Field(..., description="Starlisting ID")
    exchange: str = Field(..., description="Exchange name")
    exchange_display: str = Field(..., description="Exchange display name")
    coin: str = Field(..., description="Base asset symbol")
    coin_name: str = Field(..., description="Base asset full name")
    quote: str = Field(..., description="Quote asset symbol")
    quote_name: str = Field(..., description="Quote asset full name")
    trading_pair: str = Field(..., description="Trading pair (e.g., BTC/USD)")
    market_type: str = Field(..., description="Market type")
    market_type_display: str = Field(..., description="Market type display name")
    interval: str = Field(..., description="Time interval")
    interval_seconds: int = Field(..., description="Interval in seconds")
    active: bool = Field(..., description="Whether this starlisting is active")


class StarlistingListResponse(BaseModel):
    """Response model for list of starlistings."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "starlistings": [
                    {
                        "id": 1,
                        "exchange": "hyperliquid",
                        "exchange_display": "Hyperliquid",
                        "coin": "BTC",
                        "coin_name": "Bitcoin",
                        "quote": "USD",
                        "quote_name": "US Dollar",
                        "trading_pair": "BTC/USD",
                        "market_type": "perps",
                        "market_type_display": "Perpetuals",
                        "interval": "15m",
                        "interval_seconds": 900,
                        "active": True,
                    }
                ],
                "total_count": 1,
            }
        }
    )

    starlistings: list[StarlistingResponse] = Field(..., description="List of starlistings")
    total_count: int = Field(..., description="Total number of starlistings")
