"""
OpenInterest model - open interest data (TimescaleDB hypertable).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class OpenInterest(Base, CreatedAtMixin):
    """
    Open interest data for perpetual/futures contracts (TimescaleDB hypertable).

    Attributes:
        listing_id: Foreign key to Listing
        timestamp: Open interest timestamp (partition key)
        open_interest: Open interest in contracts/coins
        open_interest_value: Open interest value in USD (if available)
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
        comment="Open interest timestamp (partition key)",
    )

    open_interest: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=False,
        comment="Open interest in contracts/coins",
    )

    open_interest_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=30, scale=2),
        nullable=True,
        comment="Open interest value in USD",
    )

    # Relationship
    listing: Mapped["Listing"] = relationship("Listing", back_populates="open_interest")

    # Indexes
    __table_args__ = (Index("idx_open_interest_listing_time", "listing_id", "timestamp"),)

    def __repr__(self) -> str:
        return (
            f"<OpenInterest(listing_id={self.listing_id}, timestamp={self.timestamp}, "
            f"oi={self.open_interest})>"
        )
