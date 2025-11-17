"""Integration tests for funding rate and open interest API endpoints."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.db.models import FundingRate, OpenInterest


@pytest.mark.integration
class TestFundingRateEndpoint:
    """Test funding rate API endpoint."""

    @pytest.mark.asyncio
    async def test_get_funding_rates_success(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test successfully retrieving funding rates."""
        # Insert test funding rates
        starlisting = seed_starlistings[0]

        test_funding_rates = [
            FundingRate(
                starlisting_id=starlisting.id,
                time=datetime(2024, 11, 16, 12, i, 0, tzinfo=timezone.utc),
                funding_rate=Decimal("0.0001"),
                premium=Decimal("0.00005"),
                mark_price=Decimal("94500.0"),
                index_price=Decimal("94495.0"),
                oracle_price=Decimal("94495.0"),
                mid_price=Decimal("94500.0"),
                next_funding_time=datetime(2024, 11, 16, 13, 0, 0, tzinfo=timezone.utc),
            )
            for i in range(10)
        ]
        db_session.add_all(test_funding_rates)
        await db_session.commit()

        # Get exchange/coin/quote/market_type from starlisting
        # Manually load relationships to avoid lazy loading issues
        await db_session.refresh(starlisting)
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType

        exchange = await db_session.scalar(
            select(Exchange).where(Exchange.id == starlisting.exchange_id)
        )
        coin = await db_session.scalar(
            select(Coin).where(Coin.id == starlisting.coin_id)
        )
        quote = await db_session.scalar(
            select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
        )
        market_type = await db_session.scalar(
            select(MarketType).where(MarketType.id == starlisting.market_type_id)
        )

        # Make request
        response = await async_client.get(
            f"/funding/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}?limit=5"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data" in data
        assert "metadata" in data
        assert len(data["data"]) == 5

        # Verify first funding rate
        first_rate = data["data"][0]
        assert "time" in first_rate
        assert "funding_rate" in first_rate
        assert "premium" in first_rate
        assert "mark_price" in first_rate
        assert "index_price" in first_rate
        assert "oracle_price" in first_rate
        assert "mid_price" in first_rate
        assert "next_funding_time" in first_rate

        # Verify metadata
        metadata = data["metadata"]
        assert metadata["exchange"] == exchange.name
        assert metadata["coin"] == coin.symbol
        assert metadata["quote"] == quote.symbol
        assert metadata["trading_pair"] == f"{coin.symbol}/{quote.symbol}"
        assert metadata["market_type"] == market_type.name
        assert metadata["count"] == 5

    @pytest.mark.asyncio
    async def test_get_funding_rates_with_time_filter(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test funding rates with time filter."""
        starlisting = seed_starlistings[0]

        # Insert funding rates over a time range
        test_funding_rates = [
            FundingRate(
                starlisting_id=starlisting.id,
                time=datetime(2024, 11, 16, 12, i, 0, tzinfo=timezone.utc),
                funding_rate=Decimal("0.0001"),
                premium=Decimal("0.00005"),
                mark_price=Decimal("94500.0"),
            )
            for i in range(20)
        ]
        db_session.add_all(test_funding_rates)
        await db_session.commit()

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType

        exchange = await db_session.scalar(
            select(Exchange).where(Exchange.id == starlisting.exchange_id)
        )
        coin = await db_session.scalar(
            select(Coin).where(Coin.id == starlisting.coin_id)
        )
        quote = await db_session.scalar(
            select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
        )
        market_type = await db_session.scalar(
            select(MarketType).where(MarketType.id == starlisting.market_type_id)
        )

        # Request with time filter
        start_time = "2024-11-16T12:05:00Z"
        end_time = "2024-11-16T12:10:00Z"

        response = await async_client.get(
            f"/funding/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}"
            f"?start_time={start_time}&end_time={end_time}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should get 5 rates (12:05, 12:06, 12:07, 12:08, 12:09)
        assert len(data["data"]) == 5

    @pytest.mark.asyncio
    async def test_get_funding_rates_not_found(
        self, async_client: AsyncClient, seed_base_data
    ):
        """Test funding rates for non-existent trading pair."""
        response = await async_client.get(
            "/funding/invalid_exchange/BTC/USD/perps"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_funding_rates_inactive_starlisting(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test funding rates for inactive starlisting."""
        # Deactivate a starlisting
        starlisting = seed_starlistings[0]
        starlisting.active = False
        await db_session.commit()

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType

        exchange = await db_session.scalar(
            select(Exchange).where(Exchange.id == starlisting.exchange_id)
        )
        coin = await db_session.scalar(
            select(Coin).where(Coin.id == starlisting.coin_id)
        )
        quote = await db_session.scalar(
            select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
        )
        market_type = await db_session.scalar(
            select(MarketType).where(MarketType.id == starlisting.market_type_id)
        )

        response = await async_client.get(
            f"/funding/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}"
        )

        assert response.status_code == 400
        assert "not active" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_funding_rates_empty(
        self, async_client: AsyncClient, seed_base_data, seed_starlistings
    ):
        """Test funding rates when no data exists."""
        starlisting = seed_starlistings[0]

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType
        from src.api.dependencies import get_db_session

        async for session in get_db_session():
            exchange = await session.scalar(
                select(Exchange).where(Exchange.id == starlisting.exchange_id)
            )
            coin = await session.scalar(
                select(Coin).where(Coin.id == starlisting.coin_id)
            )
            quote = await session.scalar(
                select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
            )
            market_type = await session.scalar(
                select(MarketType).where(MarketType.id == starlisting.market_type_id)
            )
            break

        response = await async_client.get(
            f"/funding/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0
        assert data["metadata"]["count"] == 0


@pytest.mark.integration
class TestOpenInterestEndpoint:
    """Test open interest API endpoint."""

    @pytest.mark.asyncio
    async def test_get_open_interest_success(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test successfully retrieving open interest."""
        # Insert test open interest records
        starlisting = seed_starlistings[0]

        test_oi_records = [
            OpenInterest(
                starlisting_id=starlisting.id,
                time=datetime(2024, 11, 16, 12, i, 0, tzinfo=timezone.utc),
                open_interest=Decimal("30000.5"),
                notional_value=Decimal("2835000000.0"),
                day_base_volume=Decimal("21000.0"),
                day_notional_volume=Decimal("2000000000.0"),
            )
            for i in range(10)
        ]
        db_session.add_all(test_oi_records)
        await db_session.commit()

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType

        exchange = await db_session.scalar(
            select(Exchange).where(Exchange.id == starlisting.exchange_id)
        )
        coin = await db_session.scalar(
            select(Coin).where(Coin.id == starlisting.coin_id)
        )
        quote = await db_session.scalar(
            select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
        )
        market_type = await db_session.scalar(
            select(MarketType).where(MarketType.id == starlisting.market_type_id)
        )

        # Make request
        response = await async_client.get(
            f"/open-interest/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}?limit=5"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data" in data
        assert "metadata" in data
        assert len(data["data"]) == 5

        # Verify first OI record
        first_oi = data["data"][0]
        assert "time" in first_oi
        assert "open_interest" in first_oi
        assert "notional_value" in first_oi
        assert "day_base_volume" in first_oi
        assert "day_notional_volume" in first_oi

        # Verify metadata
        metadata = data["metadata"]
        assert metadata["exchange"] == exchange.name
        assert metadata["coin"] == coin.symbol
        assert metadata["quote"] == quote.symbol
        assert metadata["trading_pair"] == f"{coin.symbol}/{quote.symbol}"
        assert metadata["market_type"] == market_type.name
        assert metadata["count"] == 5

    @pytest.mark.asyncio
    async def test_get_open_interest_with_time_filter(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test open interest with time filter."""
        starlisting = seed_starlistings[0]

        # Insert OI records over a time range
        test_oi_records = [
            OpenInterest(
                starlisting_id=starlisting.id,
                time=datetime(2024, 11, 16, 12, i, 0, tzinfo=timezone.utc),
                open_interest=Decimal("30000.5"),
                notional_value=Decimal("2835000000.0"),
            )
            for i in range(20)
        ]
        db_session.add_all(test_oi_records)
        await db_session.commit()

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType

        exchange = await db_session.scalar(
            select(Exchange).where(Exchange.id == starlisting.exchange_id)
        )
        coin = await db_session.scalar(
            select(Coin).where(Coin.id == starlisting.coin_id)
        )
        quote = await db_session.scalar(
            select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
        )
        market_type = await db_session.scalar(
            select(MarketType).where(MarketType.id == starlisting.market_type_id)
        )

        # Request with time filter
        start_time = "2024-11-16T12:05:00Z"
        end_time = "2024-11-16T12:10:00Z"

        response = await async_client.get(
            f"/open-interest/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}"
            f"?start_time={start_time}&end_time={end_time}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should get 5 records (12:05, 12:06, 12:07, 12:08, 12:09)
        assert len(data["data"]) == 5

    @pytest.mark.asyncio
    async def test_get_open_interest_not_found(
        self, async_client: AsyncClient, seed_base_data
    ):
        """Test open interest for non-existent trading pair."""
        response = await async_client.get(
            "/open-interest/invalid_exchange/BTC/USD/perps"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_open_interest_empty(
        self, async_client: AsyncClient, seed_base_data, seed_starlistings
    ):
        """Test open interest when no data exists."""
        starlisting = seed_starlistings[0]

        # Get starlisting components
        from sqlalchemy import select
        from src.db.models import Exchange, Coin, QuoteCurrency, MarketType
        from src.api.dependencies import get_db_session

        async for session in get_db_session():
            exchange = await session.scalar(
                select(Exchange).where(Exchange.id == starlisting.exchange_id)
            )
            coin = await session.scalar(
                select(Coin).where(Coin.id == starlisting.coin_id)
            )
            quote = await session.scalar(
                select(QuoteCurrency).where(QuoteCurrency.id == starlisting.quote_currency_id)
            )
            market_type = await session.scalar(
                select(MarketType).where(MarketType.id == starlisting.market_type_id)
            )
            break

        response = await async_client.get(
            f"/open-interest/{exchange.name}/{coin.symbol}/{quote.symbol}/{market_type.name}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0
        assert data["metadata"]["count"] == 0
