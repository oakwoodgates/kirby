"""
ListingType model - represents trading types (perps, spot, futures, options).
"""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ListingType(Base):
    """
    Trading type (perps, spot, futures, options).

    Attributes:
        id: Primary key
        type: Type name (e.g., 'perps', 'spot', 'futures', 'options')
        description: Human-readable description
    """

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    type: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Trading type (lowercase, unique)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of the listing type",
    )

    # Relationships
    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="listing_type",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ListingType(id={self.id}, type='{self.type}')>"
