"""
MarketMetadata model - market ticker snapshots (TimescaleDB hypertable).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class MarketMetadata(Base, CreatedAtMixin):
    """
    Market ticker snapshot data (TimescaleDB hypertable).

    Captures periodic snapshots of market state (bid, ask, volume, etc.).

    Attributes:
        listing_id: Foreign key to Listing
        timestamp: Snapshot timestamp (partition key)
        bid: Best bid price
        ask: Best ask price
        last_price: Last traded price
        volume_24h: 24-hour trading volume (base currency)
        volume_quote_24h: 24-hour trading volume (quote currency/USD)
        price_change_24h: 24-hour price change (absolute)
        percentage_change_24h: 24-hour percentage change
        high_24h: 24-hour high price
        low_24h: 24-hour low price
        data: Additional exchange-specific fields (JSONB)
        created_at: When this record was inserted
    """

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listing.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Foreign key to Listing",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        comment="Snapshot timestamp (partition key)",
    )

    bid: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Best bid price",
    )

    ask: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Best ask price",
    )

    last_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Last traded price",
    )

    volume_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=True,
        comment="24-hour trading volume (base currency)",
    )

    volume_quote_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=2),
        nullable=True,
        comment="24-hour trading volume (quote currency/USD)",
    )

    price_change_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="24-hour price change (absolute)",
    )

    percentage_change_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="24-hour percentage change",
    )

    high_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="24-hour high price",
    )

    low_24h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="24-hour low price",
    )

    data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional exchange-specific fields",
    )

    # Relationship
    listing: Mapped["Listing"] = relationship("Listing", back_populates="market_metadata")

    # Indexes
    __table_args__ = (Index("idx_market_metadata_listing_time", "listing_id", "timestamp"),)

    def __repr__(self) -> str:
        return (
            f"<MarketMetadata(listing_id={self.listing_id}, timestamp={self.timestamp}, "
            f"last_price={self.last_price})>"
        )
