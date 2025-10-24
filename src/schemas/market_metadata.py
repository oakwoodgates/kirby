"""
Pydantic schemas for MarketMetadata (ticker) data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketMetadataSchema(BaseModel):
    """Base market metadata schema for validation."""

    listing_id: int = Field(..., gt=0, description="Listing ID")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    bid: Optional[Decimal] = Field(None, gt=0, description="Best bid price")
    ask: Optional[Decimal] = Field(None, gt=0, description="Best ask price")
    last_price: Optional[Decimal] = Field(None, gt=0, description="Last traded price")
    volume_24h: Optional[Decimal] = Field(None, ge=0, description="24h volume (base currency)")
    volume_quote_24h: Optional[Decimal] = Field(None, ge=0, description="24h volume (quote currency/USD)")
    price_change_24h: Optional[Decimal] = Field(None, description="24h price change (absolute)")
    percentage_change_24h: Optional[Decimal] = Field(None, description="24h percentage change")
    high_24h: Optional[Decimal] = Field(None, gt=0, description="24h high price")
    low_24h: Optional[Decimal] = Field(None, gt=0, description="24h low price")
    data: Optional[dict[str, Any]] = Field(None, description="Additional exchange-specific fields")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "listing_id": 1,
                "timestamp": "2025-01-23T12:00:00Z",
                "bid": "49990.00",
                "ask": "50010.00",
                "last_price": "50000.00",
                "volume_24h": "12500.5",
                "volume_quote_24h": "625000000.00",
                "price_change_24h": "500.00",
                "percentage_change_24h": "1.01",
                "high_24h": "50500.00",
                "low_24h": "49000.00",
            }
        },
    }


class MarketMetadataCreate(MarketMetadataSchema):
    """Schema for creating market metadata."""

    pass


class MarketMetadataResponse(MarketMetadataSchema):
    """Schema for market metadata API response."""

    created_at: datetime = Field(..., description="When this record was created")

    model_config = {
        "from_attributes": True,
    }
