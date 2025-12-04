"""
Repository pattern for database access.
"""
from datetime import datetime
from decimal import Decimal
from typing import Generic, List, TypeVar

import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Candle,
    Coin,
    Exchange,
    FundingRate,
    Interval,
    MarketType,
    OpenInterest,
    QuoteCurrency,
    Starlisting,
)

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get a record by ID."""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = True) -> List[ModelType]:
        """Get all records."""
        query = select(self.model)
        if active_only and hasattr(self.model, "active"):
            query = query.where(self.model.active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs) -> ModelType | None:
        """Update a record by ID."""
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
            await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        instance = await self.get_by_id(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False


class ExchangeRepository(BaseRepository[Exchange]):
    """Repository for Exchange model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Exchange)

    async def get_by_name(self, name: str) -> Exchange | None:
        """Get exchange by name."""
        result = await self.session.execute(select(Exchange).where(Exchange.name == name))
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str, display_name: str) -> Exchange:
        """Get or create an exchange."""
        exchange = await self.get_by_name(name)
        if not exchange:
            exchange = await self.create(name=name, display_name=display_name, active=True)
            await self.session.commit()
        return exchange


class CoinRepository(BaseRepository[Coin]):
    """Repository for Coin model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Coin)

    async def get_by_symbol(self, symbol: str) -> Coin | None:
        """Get coin by symbol."""
        result = await self.session.execute(select(Coin).where(Coin.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_or_create(self, symbol: str, name: str) -> Coin:
        """Get or create a coin."""
        coin = await self.get_by_symbol(symbol)
        if not coin:
            coin = await self.create(symbol=symbol, name=name, active=True)
            await self.session.commit()
        return coin


class QuoteCurrencyRepository(BaseRepository[QuoteCurrency]):
    """Repository for QuoteCurrency model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, QuoteCurrency)

    async def get_by_symbol(self, symbol: str) -> QuoteCurrency | None:
        """Get quote currency by symbol."""
        result = await self.session.execute(select(QuoteCurrency).where(QuoteCurrency.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_or_create(self, symbol: str, name: str) -> QuoteCurrency:
        """Get or create a quote currency."""
        quote = await self.get_by_symbol(symbol)
        if not quote:
            quote = await self.create(symbol=symbol, name=name, active=True)
            await self.session.commit()
        return quote


class MarketTypeRepository(BaseRepository[MarketType]):
    """Repository for MarketType model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, MarketType)

    async def get_by_name(self, name: str) -> MarketType | None:
        """Get market type by name."""
        result = await self.session.execute(select(MarketType).where(MarketType.name == name))
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str, display_name: str) -> MarketType:
        """Get or create a market type."""
        market_type = await self.get_by_name(name)
        if not market_type:
            market_type = await self.create(name=name, display_name=display_name, active=True)
            await self.session.commit()
        return market_type


class IntervalRepository(BaseRepository[Interval]):
    """Repository for Interval model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Interval)

    async def get_by_name(self, name: str) -> Interval | None:
        """Get interval by name."""
        result = await self.session.execute(select(Interval).where(Interval.name == name))
        return result.scalar_one_or_none()


class StarlistingRepository(BaseRepository[Starlisting]):
    """Repository for Starlisting model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Starlisting)

    async def get_by_components(
        self,
        exchange_id: int,
        coin_id: int,
        quote_currency_id: int,
        market_type_id: int,
        interval_id: int,
    ) -> Starlisting | None:
        """Get starlisting by its component IDs."""
        result = await self.session.execute(
            select(Starlisting).where(
                Starlisting.exchange_id == exchange_id,
                Starlisting.coin_id == coin_id,
                Starlisting.quote_currency_id == quote_currency_id,
                Starlisting.market_type_id == market_type_id,
                Starlisting.interval_id == interval_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_starlistings(self) -> List[Starlisting]:
        """Get all active starlistings with relationships loaded."""
        result = await self.session.execute(
            select(Starlisting)
            .where(Starlisting.active == True)
            .options(
                selectinload(Starlisting.exchange),
                selectinload(Starlisting.coin),
                selectinload(Starlisting.quote_currency),
                selectinload(Starlisting.market_type),
                selectinload(Starlisting.interval),
            )
        )
        return list(result.scalars().all())

    async def get_active(self) -> List[Starlisting]:
        """Alias for get_active_starlistings() for consistency."""
        return await self.get_active_starlistings()

    async def get_by_id_with_relations(self, starlisting_id: int) -> Starlisting | None:
        """Get starlisting by ID with all relationships eagerly loaded."""
        result = await self.session.execute(
            select(Starlisting)
            .where(Starlisting.id == starlisting_id)
            .options(
                selectinload(Starlisting.exchange),
                selectinload(Starlisting.coin),
                selectinload(Starlisting.quote_currency),
                selectinload(Starlisting.market_type),
                selectinload(Starlisting.interval),
            )
        )
        return result.scalar_one_or_none()


class CandleRepository:
    """
    Repository for Candle model.
    Uses asyncpg for high-performance bulk inserts.
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def bulk_insert(self, candles: List[dict]) -> int:
        """
        Bulk insert candles using asyncpg COPY.

        Args:
            candles: List of candle dictionaries with keys:
                time, starlisting_id, open, high, low, close, volume, num_trades

        Returns:
            Number of rows inserted
        """
        if not candles:
            return 0

        # Prepare data for COPY
        records = [
            (
                candle["time"],
                candle["starlisting_id"],
                Decimal(str(candle["open"])),
                Decimal(str(candle["high"])),
                Decimal(str(candle["low"])),
                Decimal(str(candle["close"])),
                Decimal(str(candle["volume"])),
                candle.get("num_trades"),
            )
            for candle in candles
        ]

        async with self.pool.acquire() as conn:
            # Use COPY for maximum performance
            result = await conn.copy_records_to_table(
                "candles",
                records=records,
                columns=["time", "starlisting_id", "open", "high", "low", "close", "volume", "num_trades"],
            )

        return len(records)

    async def upsert_candles(self, candles: List[dict]) -> int:
        """
        Upsert candles (insert or update on conflict).

        Args:
            candles: List of candle dictionaries

        Returns:
            Number of rows affected
        """
        if not candles:
            return 0

        query = """
            INSERT INTO candles (time, starlisting_id, open, high, low, close, volume, num_trades)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (time, starlisting_id)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                num_trades = COALESCE(EXCLUDED.num_trades, candles.num_trades)
        """

        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [
                    (
                        candle["time"],
                        candle["starlisting_id"],
                        Decimal(str(candle["open"])),
                        Decimal(str(candle["high"])),
                        Decimal(str(candle["low"])),
                        Decimal(str(candle["close"])),
                        Decimal(str(candle["volume"])),
                        candle.get("num_trades"),
                    )
                    for candle in candles
                ],
            )

        return len(candles)

    async def get_latest_candle(
        self,
        session: AsyncSession,
        starlisting_id: int,
    ) -> Candle | None:
        """Get the latest candle for a starlisting."""
        result = await session.execute(
            select(Candle)
            .where(Candle.starlisting_id == starlisting_id)
            .order_by(Candle.time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_candles(
        self,
        session: AsyncSession,
        starlisting_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> List[Candle]:
        """
        Get candles for a starlisting within a time range.

        Args:
            session: SQLAlchemy session
            starlisting_id: Starlisting ID
            start_time: Start time (inclusive)
            end_time: End time (exclusive)
            limit: Maximum number of candles to return

        Returns:
            List of Candle objects
        """
        query = select(Candle).where(Candle.starlisting_id == starlisting_id)

        if start_time:
            query = query.where(Candle.time >= start_time)
        if end_time:
            query = query.where(Candle.time < end_time)

        query = query.order_by(Candle.time.asc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


class FundingRateRepository:
    """
    Repository for FundingRate model.
    Uses asyncpg for high-performance inserts, SQLAlchemy for queries.
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upsert_funding_rates(self, funding_rates: List[dict]) -> int:
        """
        Upsert funding rates (insert or update on conflict).

        Args:
            funding_rates: List of funding rate dictionaries with keys:
                time, trading_pair_id, funding_rate, premium, mark_price,
                index_price, oracle_price, mid_price, next_funding_time

        Returns:
            Number of rows affected
        """
        if not funding_rates:
            return 0

        query = """
            INSERT INTO funding_rates (
                time, trading_pair_id, funding_rate, premium,
                mark_price, index_price, oracle_price, mid_price, next_funding_time
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (trading_pair_id, time)
            DO UPDATE SET
                funding_rate = EXCLUDED.funding_rate,
                premium = EXCLUDED.premium,
                mark_price = EXCLUDED.mark_price,
                index_price = EXCLUDED.index_price,
                oracle_price = EXCLUDED.oracle_price,
                mid_price = EXCLUDED.mid_price,
                next_funding_time = EXCLUDED.next_funding_time
        """

        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [
                    (
                        rate["time"],
                        rate["trading_pair_id"],
                        Decimal(str(rate["funding_rate"])),
                        Decimal(str(rate["premium"])) if rate.get("premium") is not None else None,
                        Decimal(str(rate["mark_price"])) if rate.get("mark_price") is not None else None,
                        Decimal(str(rate["index_price"])) if rate.get("index_price") is not None else None,
                        Decimal(str(rate["oracle_price"])) if rate.get("oracle_price") is not None else None,
                        Decimal(str(rate["mid_price"])) if rate.get("mid_price") is not None else None,
                        rate.get("next_funding_time"),
                    )
                    for rate in funding_rates
                ],
            )

        return len(funding_rates)

    async def get_latest_funding_rate(
        self,
        session: AsyncSession,
        starlisting_id: int,
    ) -> FundingRate | None:
        """Get the latest funding rate for a starlisting.

        Since funding rates are stored per trading_pair_id, this method
        joins through the starlisting's trading_pair to find the rate.
        """
        from src.db.models import Starlisting

        result = await session.execute(
            select(FundingRate)
            .join(Starlisting, FundingRate.trading_pair_id == Starlisting.trading_pair_id)
            .where(Starlisting.id == starlisting_id)
            .order_by(FundingRate.time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_funding_rates(
        self,
        session: AsyncSession,
        starlisting_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> List[FundingRate]:
        """
        Get funding rates for a starlisting within a time range.

        Since funding rates are stored per trading_pair_id, this method
        joins through the starlisting's trading_pair to find the rates.

        Args:
            session: SQLAlchemy session
            starlisting_id: Starlisting ID
            start_time: Start time (inclusive)
            end_time: End time (exclusive)
            limit: Maximum number of funding rates to return

        Returns:
            List of FundingRate objects
        """
        from src.db.models import Starlisting

        query = (
            select(FundingRate)
            .join(Starlisting, FundingRate.trading_pair_id == Starlisting.trading_pair_id)
            .where(Starlisting.id == starlisting_id)
        )

        if start_time:
            query = query.where(FundingRate.time >= start_time)
        if end_time:
            query = query.where(FundingRate.time < end_time)

        query = query.order_by(FundingRate.time.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


class OpenInterestRepository:
    """
    Repository for OpenInterest model.
    Uses asyncpg for high-performance inserts, SQLAlchemy for queries.
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upsert_open_interest(self, open_interest_records: List[dict]) -> int:
        """
        Upsert open interest records (insert or update on conflict).

        Args:
            open_interest_records: List of open interest dictionaries with keys:
                time, trading_pair_id, open_interest, notional_value,
                day_base_volume, day_notional_volume

        Returns:
            Number of rows affected
        """
        if not open_interest_records:
            return 0

        query = """
            INSERT INTO open_interest (
                time, trading_pair_id, open_interest, notional_value,
                day_base_volume, day_notional_volume
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (trading_pair_id, time)
            DO UPDATE SET
                open_interest = EXCLUDED.open_interest,
                notional_value = EXCLUDED.notional_value,
                day_base_volume = EXCLUDED.day_base_volume,
                day_notional_volume = EXCLUDED.day_notional_volume
        """

        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [
                    (
                        record["time"],
                        record["trading_pair_id"],
                        Decimal(str(record["open_interest"])),
                        Decimal(str(record["notional_value"])) if record.get("notional_value") is not None else None,
                        Decimal(str(record["day_base_volume"])) if record.get("day_base_volume") is not None else None,
                        Decimal(str(record["day_notional_volume"])) if record.get("day_notional_volume") is not None else None,
                    )
                    for record in open_interest_records
                ],
            )

        return len(open_interest_records)

    async def get_latest_open_interest(
        self,
        session: AsyncSession,
        starlisting_id: int,
    ) -> OpenInterest | None:
        """Get the latest open interest record for a starlisting.

        Since open interest is stored per trading_pair_id, this method
        joins through the starlisting's trading_pair to find the record.
        """
        from src.db.models import Starlisting

        result = await session.execute(
            select(OpenInterest)
            .join(Starlisting, OpenInterest.trading_pair_id == Starlisting.trading_pair_id)
            .where(Starlisting.id == starlisting_id)
            .order_by(OpenInterest.time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_open_interest(
        self,
        session: AsyncSession,
        starlisting_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> List[OpenInterest]:
        """
        Get open interest records for a starlisting within a time range.

        Since open interest is stored per trading_pair_id, this method
        joins through the starlisting's trading_pair to find the records.

        Args:
            session: SQLAlchemy session
            starlisting_id: Starlisting ID
            start_time: Start time (inclusive)
            end_time: End time (exclusive)
            limit: Maximum number of records to return

        Returns:
            List of OpenInterest objects
        """
        from src.db.models import Starlisting

        query = (
            select(OpenInterest)
            .join(Starlisting, OpenInterest.trading_pair_id == Starlisting.trading_pair_id)
            .where(Starlisting.id == starlisting_id)
        )

        if start_time:
            query = query.where(OpenInterest.time >= start_time)
        if end_time:
            query = query.where(OpenInterest.time < end_time)

        query = query.order_by(OpenInterest.time.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())
