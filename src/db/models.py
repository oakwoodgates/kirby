"""
Database models for Kirby.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Exchange(Base, TimestampMixin):
    """Exchange model - represents a cryptocurrency exchange."""

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    starlistings: Mapped[List["Starlisting"]] = relationship(
        "Starlisting", back_populates="exchange"
    )

    def __repr__(self) -> str:
        return f"<Exchange(id={self.id}, name={self.name})>"


class Coin(Base, TimestampMixin):
    """Coin model - represents a cryptocurrency (base asset)."""

    __tablename__ = "coins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    starlistings: Mapped[List["Starlisting"]] = relationship(
        "Starlisting", back_populates="coin"
    )

    def __repr__(self) -> str:
        return f"<Coin(id={self.id}, symbol={self.symbol}, name={self.name})>"


class QuoteCurrency(Base, TimestampMixin):
    """QuoteCurrency model - represents the quote asset in a trading pair (USD, USDC, EUR, etc.)."""

    __tablename__ = "quote_currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    starlistings: Mapped[List["Starlisting"]] = relationship(
        "Starlisting", back_populates="quote_currency"
    )

    def __repr__(self) -> str:
        return f"<QuoteCurrency(id={self.id}, symbol={self.symbol}, name={self.name})>"


class MarketType(Base, TimestampMixin):
    """MarketType model - represents market type (spot, perps, futures, etc.)."""

    __tablename__ = "market_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    starlistings: Mapped[List["Starlisting"]] = relationship(
        "Starlisting", back_populates="market_type"
    )

    def __repr__(self) -> str:
        return f"<MarketType(id={self.id}, name={self.name})>"


class Interval(Base, TimestampMixin):
    """Interval model - represents time intervals (1m, 15m, 4h, 1d, etc.)."""

    __tablename__ = "intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    starlistings: Mapped[List["Starlisting"]] = relationship(
        "Starlisting", back_populates="interval"
    )

    __table_args__ = (CheckConstraint("seconds > 0", name="positive_seconds"),)

    def __repr__(self) -> str:
        return f"<Interval(id={self.id}, name={self.name}, seconds={self.seconds})>"


class Starlisting(Base, TimestampMixin):
    """
    Starlisting model - represents a unique combination of exchange, trading pair (coin+quote),
    market type, and interval. This is what we collect and store data for.

    Example: Hyperliquid BTC/USD Perpetuals 15m
    """

    __tablename__ = "starlistings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exchanges.id"), nullable=False
    )
    coin_id: Mapped[int] = mapped_column(Integer, ForeignKey("coins.id"), nullable=False)
    quote_currency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quote_currencies.id"), nullable=False
    )
    market_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_types.id"), nullable=False
    )
    interval_id: Mapped[int] = mapped_column(Integer, ForeignKey("intervals.id"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    exchange: Mapped["Exchange"] = relationship("Exchange", back_populates="starlistings")
    coin: Mapped["Coin"] = relationship("Coin", back_populates="starlistings")
    quote_currency: Mapped["QuoteCurrency"] = relationship("QuoteCurrency", back_populates="starlistings")
    market_type: Mapped["MarketType"] = relationship("MarketType", back_populates="starlistings")
    interval: Mapped["Interval"] = relationship("Interval", back_populates="starlistings")
    candles: Mapped[List["Candle"]] = relationship("Candle", back_populates="starlisting")

    __table_args__ = (
        UniqueConstraint(
            "exchange_id",
            "coin_id",
            "quote_currency_id",
            "market_type_id",
            "interval_id",
            name="uq_starlisting",
        ),
        Index(
            "ix_starlisting_lookup",
            "exchange_id",
            "coin_id",
            "quote_currency_id",
            "market_type_id",
            "interval_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Starlisting(id={self.id}, exchange_id={self.exchange_id}, "
            f"coin_id={self.coin_id}, quote_currency_id={self.quote_currency_id}, "
            f"market_type_id={self.market_type_id}, interval_id={self.interval_id})>"
        )

    def get_trading_pair(self) -> str:
        """Get the trading pair symbol (e.g., 'BTC/USD')."""
        return f"{self.coin.symbol}/{self.quote_currency.symbol}"


class Candle(Base):
    """
    Candle model - represents OHLCV candle data.
    This will be converted to a TimescaleDB hypertable.
    """

    __tablename__ = "candles"

    time: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)
    starlisting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("starlistings.id"),
        primary_key=True,
        nullable=False,
    )

    # OHLCV data
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)

    # Additional metadata
    num_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationship
    starlisting: Mapped["Starlisting"] = relationship("Starlisting", back_populates="candles")

    __table_args__ = (
        # Ensure OHLC consistency
        CheckConstraint("high >= low", name="valid_high_low"),
        CheckConstraint("high >= open", name="valid_high_open"),
        CheckConstraint("high >= close", name="valid_high_close"),
        CheckConstraint("low <= open", name="valid_low_open"),
        CheckConstraint("low <= close", name="valid_low_close"),
        CheckConstraint("open > 0", name="positive_open"),
        CheckConstraint("high > 0", name="positive_high"),
        CheckConstraint("low > 0", name="positive_low"),
        CheckConstraint("close > 0", name="positive_close"),
        CheckConstraint("volume >= 0", name="non_negative_volume"),
        # Indexes for efficient queries
        Index("ix_candles_time", "time", postgresql_using="brin"),
        Index("ix_candles_starlisting_time", "starlisting_id", "time"),
    )

    def __repr__(self) -> str:
        return (
            f"<Candle(time={self.time}, starlisting_id={self.starlisting_id}, "
            f"open={self.open}, high={self.high}, low={self.low}, close={self.close}, "
            f"volume={self.volume})>"
        )


class FundingRate(Base):
    """
    FundingRate model - represents perpetual futures funding rate data.
    This will be converted to a TimescaleDB hypertable.
    """

    __tablename__ = "funding_rates"

    time: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)
    starlisting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("starlistings.id"),
        primary_key=True,
        nullable=False,
    )

    # Core funding data
    funding_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    premium: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)

    # Price context
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    index_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    oracle_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    mid_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Timing
    next_funding_time: Mapped[datetime | None] = mapped_column(nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default="now()"
    )

    # Relationship
    starlisting: Mapped["Starlisting"] = relationship("Starlisting")

    __table_args__ = (
        Index("ix_funding_rates_starlisting_time", "starlisting_id", "time"),
        Index("ix_funding_rates_time", "time"),
    )

    def __repr__(self) -> str:
        return (
            f"<FundingRate(time={self.time}, starlisting_id={self.starlisting_id}, "
            f"funding_rate={self.funding_rate}, mark_price={self.mark_price})>"
        )


class OpenInterest(Base):
    """
    OpenInterest model - represents open interest (total position size) data.
    This will be converted to a TimescaleDB hypertable.
    """

    __tablename__ = "open_interest"

    time: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)
    starlisting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("starlistings.id"),
        primary_key=True,
        nullable=False,
    )

    # Open interest data
    open_interest: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    notional_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Volume context
    day_base_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    day_notional_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default="now()"
    )

    # Relationship
    starlisting: Mapped["Starlisting"] = relationship("Starlisting")

    __table_args__ = (
        Index("ix_open_interest_starlisting_time", "starlisting_id", "time"),
        Index("ix_open_interest_time", "time"),
    )

    def __repr__(self) -> str:
        return (
            f"<OpenInterest(time={self.time}, starlisting_id={self.starlisting_id}, "
            f"open_interest={self.open_interest}, notional_value={self.notional_value})>"
        )
