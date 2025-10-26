"""
Integration tests for database repositories.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Candle, Coin, Exchange, QuoteCurrency, Starlisting
from src.db.repositories import (
    CandleRepository,
    CoinRepository,
    ExchangeRepository,
    QuoteCurrencyRepository,
    StarlistingRepository,
)


@pytest.mark.integration
class TestExchangeRepository:
    """Test exchange repository operations."""

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_session: AsyncSession, seed_base_data):
        """Test getting exchange by name."""
        repo = ExchangeRepository(db_session)
        exchange = await repo.get_by_name("hyperliquid")

        assert exchange is not None
        assert exchange.name == "hyperliquid"
        assert exchange.display_name == "Hyperliquid"
        assert exchange.active is True

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, db_session: AsyncSession):
        """Test getting non-existent exchange."""
        repo = ExchangeRepository(db_session)
        exchange = await repo.get_by_name("nonexistent")

        assert exchange is None

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, db_session: AsyncSession, seed_base_data):
        """Test get_or_create with existing exchange."""
        repo = ExchangeRepository(db_session)
        exchange = await repo.get_or_create("hyperliquid", "Hyperliquid")

        assert exchange is not None
        assert exchange.name == "hyperliquid"

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session: AsyncSession):
        """Test get_or_create with new exchange."""
        repo = ExchangeRepository(db_session)
        exchange = await repo.get_or_create("binance", "Binance")

        assert exchange is not None
        assert exchange.name == "binance"
        assert exchange.display_name == "Binance"
        assert exchange.active is True


@pytest.mark.integration
class TestCoinRepository:
    """Test coin repository operations."""

    @pytest.mark.asyncio
    async def test_get_by_symbol(self, db_session: AsyncSession, seed_base_data):
        """Test getting coin by symbol."""
        repo = CoinRepository(db_session)
        coin = await repo.get_by_symbol("BTC")

        assert coin is not None
        assert coin.symbol == "BTC"
        assert coin.name == "Bitcoin"
        assert coin.active is True

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session: AsyncSession):
        """Test get_or_create with new coin."""
        repo = CoinRepository(db_session)
        coin = await repo.get_or_create("ETH", "Ethereum")

        assert coin is not None
        assert coin.symbol == "ETH"
        assert coin.name == "Ethereum"
        assert coin.active is True


@pytest.mark.integration
class TestQuoteCurrencyRepository:
    """Test quote currency repository operations."""

    @pytest.mark.asyncio
    async def test_get_by_symbol(self, db_session: AsyncSession, seed_base_data):
        """Test getting quote currency by symbol."""
        repo = QuoteCurrencyRepository(db_session)
        quote = await repo.get_by_symbol("USD")

        assert quote is not None
        assert quote.symbol == "USD"
        assert quote.name == "US Dollar"
        assert quote.active is True

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session: AsyncSession):
        """Test get_or_create with new quote currency."""
        repo = QuoteCurrencyRepository(db_session)
        quote = await repo.get_or_create("USDT", "Tether USD")

        assert quote is not None
        assert quote.symbol == "USDT"
        assert quote.name == "Tether USD"
        assert quote.active is True


@pytest.mark.integration
class TestStarlistingRepository:
    """Test starlisting repository operations."""

    @pytest.mark.asyncio
    async def test_get_by_components(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting starlisting by components."""
        repo = StarlistingRepository(db_session)

        exchange = seed_base_data["exchange"]
        btc = seed_base_data["btc"]
        usd = seed_base_data["usd"]
        perps = seed_base_data["perps"]
        interval_1m = seed_base_data["intervals"]["1m"]

        starlisting = await repo.get_by_components(
            exchange_id=exchange.id,
            coin_id=btc.id,
            quote_currency_id=usd.id,
            market_type_id=perps.id,
            interval_id=interval_1m.id,
        )

        assert starlisting is not None
        assert starlisting.exchange_id == exchange.id
        assert starlisting.coin_id == btc.id
        assert starlisting.quote_currency_id == usd.id
        assert starlisting.market_type_id == perps.id
        assert starlisting.interval_id == interval_1m.id

    @pytest.mark.asyncio
    async def test_get_by_components_not_found(
        self, db_session: AsyncSession, seed_base_data
    ):
        """Test getting non-existent starlisting."""
        repo = StarlistingRepository(db_session)

        exchange = seed_base_data["exchange"]
        btc = seed_base_data["btc"]
        usd = seed_base_data["usd"]
        perps = seed_base_data["perps"]
        interval_1m = seed_base_data["intervals"]["1m"]

        starlisting = await repo.get_by_components(
            exchange_id=exchange.id,
            coin_id=btc.id,
            quote_currency_id=usd.id,
            market_type_id=perps.id,
            interval_id=interval_1m.id,
        )

        # Should not exist since we haven't seeded starlistings
        assert starlisting is None

    @pytest.mark.asyncio
    async def test_get_active(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting all active starlistings."""
        repo = StarlistingRepository(db_session)
        active = await repo.get_active()

        assert len(active) == len(seed_starlistings)
        assert all(s.active for s in active)

    @pytest.mark.asyncio
    async def test_trading_pair_method(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test the get_trading_pair method."""
        starlisting = seed_starlistings[0]

        # Load relationships
        await db_session.refresh(starlisting, ["coin", "quote_currency"])

        trading_pair = starlisting.get_trading_pair()

        assert "/" in trading_pair
        parts = trading_pair.split("/")
        assert len(parts) == 2
        assert parts[0] in ["BTC", "SOL"]
        assert parts[1] == "USD"


@pytest.mark.integration
class TestCandleRepository:
    """Test candle repository operations."""

    @pytest.mark.asyncio
    async def test_get_candles_empty(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting candles when none exist."""
        repo = CandleRepository(None)
        starlisting = seed_starlistings[0]

        candles = await repo.get_candles(
            session=db_session,
            starlisting_id=starlisting.id,
        )

        assert isinstance(candles, list)
        assert len(candles) == 0

    @pytest.mark.asyncio
    async def test_get_candles_with_data(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting candles with data."""
        starlisting = seed_starlistings[0]

        # Insert test candles
        test_candles = [
            Candle(
                starlisting_id=starlisting.id,
                time=datetime(2024, 1, 1, 0, i, 0, tzinfo=timezone.utc),
                open=Decimal("40000.0"),
                high=Decimal("40100.0"),
                low=Decimal("39900.0"),
                close=Decimal("40050.0"),
                volume=Decimal("1234.56"),
                num_trades=42,
            )
            for i in range(5)
        ]
        db_session.add_all(test_candles)
        await db_session.commit()

        # Get candles
        repo = CandleRepository(None)
        candles = await repo.get_candles(
            session=db_session,
            starlisting_id=starlisting.id,
        )

        assert len(candles) == 5
        assert all(isinstance(c, Candle) for c in candles)

    @pytest.mark.asyncio
    async def test_get_candles_with_limit(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting candles with limit."""
        starlisting = seed_starlistings[0]

        # Insert test candles
        test_candles = [
            Candle(
                starlisting_id=starlisting.id,
                time=datetime(2024, 1, 1, 0, i, 0, tzinfo=timezone.utc),
                open=Decimal("40000.0"),
                high=Decimal("40100.0"),
                low=Decimal("39900.0"),
                close=Decimal("40050.0"),
                volume=Decimal("1234.56"),
                num_trades=42,
            )
            for i in range(10)
        ]
        db_session.add_all(test_candles)
        await db_session.commit()

        # Get candles with limit
        repo = CandleRepository(None)
        candles = await repo.get_candles(
            session=db_session,
            starlisting_id=starlisting.id,
            limit=5,
        )

        assert len(candles) == 5

    @pytest.mark.asyncio
    async def test_get_candles_with_time_filter(
        self, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting candles with time filter."""
        starlisting = seed_starlistings[0]

        # Insert test candles
        test_candles = [
            Candle(
                starlisting_id=starlisting.id,
                time=datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc),
                open=Decimal("40000.0"),
                high=Decimal("40100.0"),
                low=Decimal("39900.0"),
                close=Decimal("40050.0"),
                volume=Decimal("1234.56"),
                num_trades=42,
            )
            for i in range(10)
        ]
        db_session.add_all(test_candles)
        await db_session.commit()

        # Get candles with time filter
        repo = CandleRepository(None)
        candles = await repo.get_candles(
            session=db_session,
            starlisting_id=starlisting.id,
            start_time=datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        )

        assert len(candles) == 3  # Hours 5, 6, 7
