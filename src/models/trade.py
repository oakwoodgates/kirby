"""
Trade model - individual trade data (TimescaleDB hypertable, optional high-volume data).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class Trade(Base, CreatedAtMixin):
    """
    Individual trade data (TimescaleDB hypertable).

    This is optional high-volume data. Enable collection per listing if needed.

    Attributes:
        listing_id: Foreign key to Listing
        timestamp: Trade timestamp (partition key)
        trade_id: Exchange-specific trade ID
        price: Trade price
        amount: Trade amount
        side: Trade side ('buy' or 'sell')
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
        comment="Trade timestamp (partition key)",
    )

    trade_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        nullable=False,
        comment="Exchange-specific trade ID",
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Trade price",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=False,
        comment="Trade amount",
    )

    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Trade side (buy or sell)",
    )

    # Relationship
    listing: Mapped["Listing"] = relationship("Listing", back_populates="trades")

    # Indexes
    __table_args__ = (Index("idx_trade_listing_time", "listing_id", "timestamp"),)

    def __repr__(self) -> str:
        return (
            f"<Trade(listing_id={self.listing_id}, timestamp={self.timestamp}, "
            f"trade_id={self.trade_id}, price={self.price}, side={self.side})>"
        )
