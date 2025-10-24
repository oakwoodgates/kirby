"""
Pydantic schemas for OpenInterest data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class OpenInterestSchema(BaseModel):
    """Base open interest schema for validation."""

    listing_id: int = Field(..., gt=0, description="Listing ID")
    timestamp: datetime = Field(..., description="Open interest timestamp")
    open_interest: Decimal = Field(..., ge=0, description="Open interest in contracts/coins")
    open_interest_value: Optional[Decimal] = Field(None, ge=0, description="Open interest value in USD")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "listing_id": 1,
                "timestamp": "2025-01-23T12:00:00Z",
                "open_interest": "125000.50",
                "open_interest_value": "6250000000.00",
            }
        },
    }


class OpenInterestCreate(OpenInterestSchema):
    """Schema for creating open interest data."""

    pass


class OpenInterestResponse(OpenInterestSchema):
    """Schema for open interest API response."""

    created_at: datetime = Field(..., description="When this record was created")

    model_config = {
        "from_attributes": True,
    }
