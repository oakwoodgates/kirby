"""
Integration tests for candle data endpoints.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Candle


@pytest.mark.integration
class TestCandlesEndpoints:
    """Test candle data API endpoints."""

    @pytest.mark.asyncio
    async def test_get_candles_starlisting_not_found(
        self, async_client: AsyncClient, seed_base_data
    ):
        """Test that non-existent starlisting returns 404."""
        response = await async_client.get(
            "/candles/hyperliquid/BTC/USD/perps/1m"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_candles_empty(
        self, async_client: AsyncClient, seed_base_data, seed_starlistings
    ):
        """Test getting candles when none exist."""
        response = await async_client.get(
            "/candles/hyperliquid/BTC/USD/perps/1m"
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "metadata" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 0

        # Verify metadata
        metadata = data["metadata"]
        assert metadata["exchange"] == "hyperliquid"
        assert metadata["coin"] == "BTC"
        assert metadata["quote"] == "USD"
        assert metadata["trading_pair"] == "BTC/USD"
        assert metadata["market_type"] == "perps"
        assert metadata["interval"] == "1m"
        assert metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_get_candles_with_data(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test getting candles with data."""
        # Insert test candles
        starlisting = seed_starlistings[0]  # BTC/USD perps 1m

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

        response = await async_client.get(
            "/candles/hyperliquid/BTC/USD/perps/1m"
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "metadata" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 5

        # Verify candle structure
        candle = data["data"][0]
        assert "time" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle
        assert "num_trades" in candle

        # Verify metadata
        metadata = data["metadata"]
        assert metadata["count"] == 5

    @pytest.mark.asyncio
    async def test_get_candles_with_limit(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test that limit parameter works."""
        # Insert test candles
        starlisting = seed_starlistings[0]  # BTC/USD perps 1m

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

        response = await async_client.get(
            "/candles/hyperliquid/BTC/USD/perps/1m?limit=5"
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 5
        assert data["metadata"]["count"] == 5

    @pytest.mark.asyncio
    async def test_get_candles_case_insensitive(
        self, async_client: AsyncClient, seed_base_data, seed_starlistings
    ):
        """Test that coin/quote symbols are case-insensitive."""
        # Test lowercase
        response = await async_client.get(
            "/candles/hyperliquid/btc/usd/perps/1m"
        )
        assert response.status_code == 200

        # Test mixed case
        response = await async_client.get(
            "/candles/hyperliquid/BtC/UsD/perps/1m"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_candles_inactive_starlisting(
        self, async_client: AsyncClient, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test that inactive starlisting returns 400."""
        # Deactivate starlisting
        starlisting = seed_starlistings[0]
        starlisting.active = False
        await db_session.commit()

        response = await async_client.get(
            "/candles/hyperliquid/BTC/USD/perps/1m"
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "not active" in data["detail"].lower()
