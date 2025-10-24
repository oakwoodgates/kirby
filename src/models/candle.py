"""
Candle model - OHLCV data (TimescaleDB hypertable).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class Candle(Base, CreatedAtMixin):
    """
    OHLCV candle data (TimescaleDB hypertable).

    This table will be converted to a hypertable partitioned by timestamp.

    Attributes:
        listing_id: Foreign key to Listing
        timestamp: Candle timestamp (partition key)
        interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
        trades_count: Number of trades (if available)
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
        comment="Candle timestamp (partition key)",
    )

    interval: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
        nullable=False,
        comment="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)",
    )

    open: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Opening price",
    )

    high: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Highest price",
    )

    low: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Lowest price",
    )

    close: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Closing price",
    )

    volume: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=False,
        comment="Trading volume",
    )

    trades_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of trades in this candle (if available)",
    )

    # Relationship
    listing: Mapped["Listing"] = relationship("Listing", back_populates="candles")

    # Indexes (in addition to PRIMARY KEY)
    __table_args__ = (
        Index("idx_candle_listing_interval_time", "listing_id", "interval", "timestamp"),
        # TimescaleDB hypertable will be created via migration
        # ALTER TABLE candles SET (timescaledb.hypertable, timescaledb.partition_column = 'timestamp');
    )

    def __repr__(self) -> str:
        return (
            f"<Candle(listing_id={self.listing_id}, timestamp={self.timestamp}, "
            f"interval={self.interval}, close={self.close})>"
        )
