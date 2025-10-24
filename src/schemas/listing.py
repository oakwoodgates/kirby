"""
Pydantic schemas for Listing data.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ListingSchema(BaseModel):
    """Base listing schema."""

    exchange_id: int = Field(..., gt=0, description="Exchange ID")
    coin_id: int = Field(..., gt=0, description="Coin ID")
    listing_type_id: int = Field(..., gt=0, description="Listing type ID")
    ccxt_symbol: str = Field(..., min_length=1, description="CCXT symbol format")
    is_active: bool = Field(default=False, description="Whether data collection is active")
    backfill_status: str = Field(default="pending", description="Backfill status")
    backfill_progress: Optional[dict[str, Any]] = Field(None, description="Backfill progress details")
    collector_config: Optional[dict[str, Any]] = Field(None, description="Collector configuration")
    metadata: Optional[dict[str, Any]] = Field(None, description="Exchange-provided metadata")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "exchange_id": 1,
                "coin_id": 1,
                "listing_type_id": 1,
                "ccxt_symbol": "BTC/USDT:USDT",
                "is_active": True,
                "backfill_status": "completed",
                "collector_config": {
                    "intervals": ["1m", "5m", "1h"],
                    "data_types": ["candles", "funding_rate", "open_interest"],
                },
            }
        },
    }


class ListingCreate(BaseModel):
    """Schema for creating a listing."""

    exchange_id: int = Field(..., gt=0, description="Exchange ID")
    coin_id: int = Field(..., gt=0, description="Coin ID")
    listing_type_id: int = Field(..., gt=0, description="Listing type ID")
    ccxt_symbol: str = Field(..., min_length=1, description="CCXT symbol format")
    collector_config: Optional[dict[str, Any]] = Field(
        default={
            "intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
            "data_types": ["candles", "funding_rate", "open_interest", "ticker"],
        },
        description="Collector configuration",
    )


class ListingUpdate(BaseModel):
    """Schema for updating a listing."""

    is_active: Optional[bool] = Field(None, description="Whether data collection is active")
    collector_config: Optional[dict[str, Any]] = Field(None, description="Collector configuration")


class ListingResponse(ListingSchema):
    """Schema for listing API response."""

    id: int = Field(..., description="Listing ID")
    created_at: datetime = Field(..., description="When the listing was created")
    updated_at: datetime = Field(..., description="When the listing was last updated")
    activated_at: Optional[datetime] = Field(None, description="When data collection was activated")

    # Related entities (optional, can be expanded)
    exchange_name: Optional[str] = Field(None, description="Exchange name")
    coin_symbol: Optional[str] = Field(None, description="Coin symbol")
    listing_type: Optional[str] = Field(None, description="Listing type")

    model_config = {
        "from_attributes": True,
    }
