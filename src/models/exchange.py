"""
Exchange model - represents cryptocurrency exchanges.
"""

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Exchange(Base, TimestampMixin):
    """
    Cryptocurrency exchange.

    Attributes:
        id: Primary key
        name: Exchange name (e.g., 'hyperliquid', 'binance', 'coinbase')
        ccxt_id: CCXT exchange identifier (nullable for custom integrations)
        is_ccxt_supported: Whether the exchange is supported by CCXT
        custom_integration_class: Python path to custom collector class (if not CCXT)
        metadata: Additional exchange-specific metadata (rate limits, capabilities, etc.)
        created_at: When the exchange was added
        updated_at: When the exchange was last modified
    """

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Exchange name (lowercase, unique)",
    )

    ccxt_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="CCXT exchange identifier (null for custom integrations)",
    )

    is_ccxt_supported: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this exchange is supported by CCXT",
    )

    custom_integration_class: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Python path to custom collector class (e.g., 'src.collectors.custom.MyCollector')",
    )

    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Exchange-specific metadata (rate limits, capabilities, etc.)",
    )

    # Relationships
    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="exchange",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Exchange(id={self.id}, name='{self.name}', ccxt_id='{self.ccxt_id}')>"
