"""
Pydantic schemas for Trade data.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class TradeSchema(BaseModel):
    """Base trade schema for validation."""

    listing_id: int = Field(..., gt=0, description="Listing ID")
    timestamp: datetime = Field(..., description="Trade timestamp")
    trade_id: str = Field(..., min_length=1, description="Exchange-specific trade ID")
    price: Decimal = Field(..., gt=0, description="Trade price")
    amount: Decimal = Field(..., gt=0, description="Trade amount")
    side: str = Field(..., description="Trade side (buy or sell)")

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate trade side."""
        v_lower = v.lower()
        if v_lower not in ["buy", "sell"]:
            raise ValueError("Side must be 'buy' or 'sell'")
        return v_lower

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "listing_id": 1,
                "timestamp": "2025-01-23T12:00:00.123Z",
                "trade_id": "1234567890",
                "price": "50000.00",
                "amount": "0.5",
                "side": "buy",
            }
        },
    }


class TradeCreate(TradeSchema):
    """Schema for creating a trade."""

    pass


class TradeResponse(TradeSchema):
    """Schema for trade API response."""

    created_at: datetime = Field(..., description="When this record was created")

    model_config = {
        "from_attributes": True,
    }
