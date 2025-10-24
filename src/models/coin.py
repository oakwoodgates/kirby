"""
Coin model - represents cryptocurrencies.
"""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class Coin(Base, CreatedAtMixin):
    """
    Cryptocurrency coin/token.

    Attributes:
        id: Primary key
        symbol: Coin symbol (e.g., 'BTC', 'HYPE', 'ETH')
        name: Full name (e.g., 'Bitcoin', 'Hyperliquid', 'Ethereum')
        coin_metadata: Additional coin-specific metadata
        created_at: When the coin was added
    """

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    symbol: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Coin symbol (uppercase, unique)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Full coin name",
    )

    coin_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Coin-specific metadata (contract address, network, etc.)",
    )

    # Relationships
    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="coin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Coin(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"
