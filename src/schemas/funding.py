"""
Pydantic schemas for funding rate and open interest data.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FundingRateResponse(BaseModel):
    """Schema for funding rate response."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime = Field(..., description="Timestamp of the funding rate snapshot")
    funding_rate: Decimal = Field(..., description="Funding rate (e.g., 0.0001 = 0.01%)")
    premium: Decimal | None = Field(None, description="Premium to index price")
    mark_price: Decimal | None = Field(None, description="Mark price of the perpetual")
    index_price: Decimal | None = Field(None, description="Index (spot) price")
    oracle_price: Decimal | None = Field(None, description="Oracle price")
    mid_price: Decimal | None = Field(None, description="Mid price (best bid + best ask) / 2")
    next_funding_time: datetime | None = Field(None, description="Next funding time")


class FundingRateMetadata(BaseModel):
    """Metadata for funding rate response."""

    exchange: str = Field(..., description="Exchange name")
    coin: str = Field(..., description="Coin symbol (base currency)")
    quote: str = Field(..., description="Quote currency symbol")
    trading_pair: str = Field(..., description="Trading pair (e.g., 'BTC/USD')")
    market_type: str = Field(..., description="Market type (e.g., 'perps')")
    count: int = Field(..., description="Number of funding rate snapshots returned")


class FundingRateListResponse(BaseModel):
    """Response schema for list of funding rates."""

    data: list[FundingRateResponse] = Field(..., description="List of funding rate snapshots")
    metadata: FundingRateMetadata = Field(..., description="Metadata about the response")


class OpenInterestResponse(BaseModel):
    """Schema for open interest response."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime = Field(..., description="Timestamp of the open interest snapshot")
    open_interest: Decimal = Field(..., description="Total open interest in base currency")
    notional_value: Decimal | None = Field(None, description="USD value of all open positions")
    day_base_volume: Decimal | None = Field(None, description="24h volume in base currency")
    day_notional_volume: Decimal | None = Field(None, description="24h volume in USD")


class OpenInterestMetadata(BaseModel):
    """Metadata for open interest response."""

    exchange: str = Field(..., description="Exchange name")
    coin: str = Field(..., description="Coin symbol (base currency)")
    quote: str = Field(..., description="Quote currency symbol")
    trading_pair: str = Field(..., description="Trading pair (e.g., 'BTC/USD')")
    market_type: str = Field(..., description="Market type (e.g., 'perps')")
    count: int = Field(..., description="Number of open interest snapshots returned")


class OpenInterestListResponse(BaseModel):
    """Response schema for list of open interest snapshots."""

    data: list[OpenInterestResponse] = Field(..., description="List of open interest snapshots")
    metadata: OpenInterestMetadata = Field(..., description="Metadata about the response")
