"""
FundingRate model - funding rate data (TimescaleDB hypertable).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class FundingRate(Base, CreatedAtMixin):
    """
    Funding rate data for perpetual contracts (TimescaleDB hypertable).

    Attributes:
        listing_id: Foreign key to Listing
        timestamp: Funding rate timestamp (partition key)
        rate: Funding rate (as decimal, e.g., 0.0001 = 0.01%)
        predicted_rate: Predicted next funding rate (if available)
        mark_price: Mark price at this timestamp
        index_price: Index/oracle price at this timestamp
        premium: Premium (mark - index)
        next_funding_time: Timestamp of next funding payment
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
        comment="Funding rate timestamp (partition key)",
    )

    rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=10),
        nullable=False,
        comment="Funding rate (as decimal)",
    )

    predicted_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=10),
        nullable=True,
        comment="Predicted next funding rate",
    )

    mark_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Mark price at this timestamp",
    )

    index_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Index/oracle price at this timestamp",
    )

    premium: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
        comment="Premium (mark_price - index_price)",
    )

    next_funding_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of next funding payment",
    )

    # Relationship
    listing: Mapped["Listing"] = relationship("Listing", back_populates="funding_rates")

    # Indexes
    __table_args__ = (Index("idx_funding_rate_listing_time", "listing_id", "timestamp"),)

    def __repr__(self) -> str:
        return (
            f"<FundingRate(listing_id={self.listing_id}, timestamp={self.timestamp}, "
            f"rate={self.rate})>"
        )
