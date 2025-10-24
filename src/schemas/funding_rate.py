"""
Pydantic schemas for FundingRate data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FundingRateSchema(BaseModel):
    """Base funding rate schema for validation."""

    listing_id: int = Field(..., gt=0, description="Listing ID")
    timestamp: datetime = Field(..., description="Funding rate timestamp")
    rate: Decimal = Field(..., description="Funding rate (as decimal, e.g., 0.0001 = 0.01%)")
    predicted_rate: Optional[Decimal] = Field(None, description="Predicted next funding rate")
    mark_price: Optional[Decimal] = Field(None, gt=0, description="Mark price")
    index_price: Optional[Decimal] = Field(None, gt=0, description="Index/oracle price")
    premium: Optional[Decimal] = Field(None, description="Premium (mark - index)")
    next_funding_time: Optional[datetime] = Field(None, description="Next funding payment time")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "listing_id": 1,
                "timestamp": "2025-01-23T12:00:00Z",
                "rate": "0.0001",
                "predicted_rate": "0.00012",
                "mark_price": "50000.00",
                "index_price": "49995.00",
                "premium": "5.00",
                "next_funding_time": "2025-01-23T13:00:00Z",
            }
        },
    }


class FundingRateCreate(FundingRateSchema):
    """Schema for creating a funding rate."""

    pass


class FundingRateResponse(FundingRateSchema):
    """Schema for funding rate API response."""

    created_at: datetime = Field(..., description="When this record was created")

    model_config = {
        "from_attributes": True,
    }
