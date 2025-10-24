"""
Pydantic schemas for Listing data.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


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
    listing_metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Exchange-provided metadata",
        serialization_alias="metadata"  # JSON output will use "metadata"
    )

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,  # Allow both 'metadata' and 'listing_metadata'
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
    """Schema for listing API response with relationship data."""

    id: int = Field(..., description="Listing ID")
    created_at: datetime = Field(..., description="When the listing was created")
    updated_at: datetime = Field(..., description="When the listing was last updated")
    activated_at: Optional[datetime] = Field(None, description="When data collection was activated")

    # Relationship data - populated from ORM relationships when available
    exchange_name: Optional[str] = Field(None, description="Exchange name")
    coin_symbol: Optional[str] = Field(None, description="Coin symbol")
    listing_type: Optional[str] = Field(None, description="Listing type")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @classmethod
    def from_orm_with_relationships(cls, listing: "Listing") -> "ListingResponse":
        """
        Create ListingResponse from ORM object, automatically extracting relationship data.
        This is the preferred way to create responses in endpoints.
        """
        # Create a dict-like object that includes relationship data
        # Pydantic's model_validate with from_attributes will read these as attributes
        class _EnrichedListing:
            def __init__(self, listing):
                self._listing = listing

            def __getattr__(self, name):
                # Handle relationship-derived fields
                if name == "exchange_name" and self._listing.exchange:
                    return self._listing.exchange.name
                elif name == "coin_symbol" and self._listing.coin:
                    return self._listing.coin.symbol
                elif name == "listing_type" and self._listing.listing_type:
                    return self._listing.listing_type.type
                # Default: get from original listing
                return getattr(self._listing, name)

        return cls.model_validate(_EnrichedListing(listing))
