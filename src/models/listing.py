"""
Listing model - represents an Exchange + Coin + Type combination.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .base import Base, TimestampMixin


class BackfillStatus(str, enum.Enum):
    """Backfill status enum."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Listing(Base, TimestampMixin):
    """
    A listing represents a tradeable market on an exchange.
    Combination of Exchange + Coin + Type (e.g., Hyperliquid + BTC + Perps).

    Attributes:
        id: Primary key
        exchange_id: Foreign key to Exchange
        coin_id: Foreign key to Coin
        listing_type_id: Foreign key to ListingType
        ccxt_symbol: CCXT symbol format (e.g., 'BTC/USDT:USDT' for perps)
        is_active: Whether data collection is active for this listing
        backfill_status: Status of historical data backfill
        backfill_progress: JSONB containing backfill progress details
        collector_config: JSONB containing collector configuration
        listing_metadata: Exchange-provided metadata for this listing
        created_at: When the listing was created
        updated_at: When the listing was last modified
        activated_at: When the listing was activated (data collection started)
    """

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    exchange_id: Mapped[int] = mapped_column(
        ForeignKey("exchange.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to Exchange",
    )

    coin_id: Mapped[int] = mapped_column(
        ForeignKey("coin.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to Coin",
    )

    listing_type_id: Mapped[int] = mapped_column(
        ForeignKey("listing_type.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to ListingType",
    )

    ccxt_symbol: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="CCXT symbol format (e.g., 'BTC/USDT:USDT')",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether data collection is active",
    )

    backfill_status: Mapped[BackfillStatus] = mapped_column(
        Enum(BackfillStatus, native_enum=False),
        default=BackfillStatus.PENDING,
        nullable=False,
        comment="Historical data backfill status",
    )

    backfill_progress: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Backfill progress details (last_timestamp, total_candles, errors, etc.)",
    )

    collector_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Collector configuration (intervals, data types, polling frequency)",
    )

    listing_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Exchange-provided metadata (leverage, decimals, min_size, etc.)",
    )

    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when data collection was activated",
    )

    # Relationships
    exchange: Mapped["Exchange"] = relationship("Exchange", back_populates="listings")
    coin: Mapped["Coin"] = relationship("Coin", back_populates="listings")
    listing_type: Mapped["ListingType"] = relationship("ListingType", back_populates="listings")

    # Candles relationship (one-to-many)
    candles: Mapped[list["Candle"]] = relationship(
        "Candle",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    # Funding rates relationship
    funding_rates: Mapped[list["FundingRate"]] = relationship(
        "FundingRate",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    # Open interest relationship
    open_interest: Mapped[list["OpenInterest"]] = relationship(
        "OpenInterest",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    # Trades relationship
    trades: Mapped[list["Trade"]] = relationship(
        "Trade",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    # Market metadata relationship
    market_metadata: Mapped[list["MarketMetadata"]] = relationship(
        "MarketMetadata",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "exchange_id",
            "coin_id",
            "listing_type_id",
            name="uq_exchange_coin_type",
        ),
        Index("idx_listing_active", "is_active"),
        Index("idx_listing_backfill_status", "backfill_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Listing(id={self.id}, exchange={self.exchange.name if self.exchange else None}, "
            f"coin={self.coin.symbol if self.coin else None}, "
            f"type={self.listing_type.type if self.listing_type else None}, "
            f"is_active={self.is_active})>"
        )
