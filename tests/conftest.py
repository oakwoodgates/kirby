"""
Pytest configuration and shared fixtures.
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.config.settings import settings
from src.db.base import Base
from src.db.models import (
    Coin,
    Exchange,
    Interval,
    MarketType,
    QuoteCurrency,
    Starlisting,
)


# Test database URL (use a separate test database)
# Replace only the database name at the end, not the username
db_url = str(settings.database_url)
if db_url.endswith("/kirby"):
    TEST_ASYNC_DATABASE_URL = db_url[:-6] + "/kirby_test"
else:
    # Fallback: replace all occurrences (for other formats)
    TEST_ASYNC_DATABASE_URL = db_url.replace("database=kirby", "database=kirby_test")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL, echo=False, future=True)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def seed_base_data(db_session: AsyncSession) -> dict[str, Any]:
    """Seed database with base reference data."""
    # Create exchange
    exchange = Exchange(
        name="hyperliquid",
        display_name="Hyperliquid",
        active=True,
    )
    db_session.add(exchange)

    # Create coins
    btc = Coin(symbol="BTC", name="Bitcoin", active=True)
    sol = Coin(symbol="SOL", name="Solana", active=True)
    db_session.add_all([btc, sol])

    # Create quote currencies
    usd = QuoteCurrency(symbol="USD", name="US Dollar", active=True)
    usdc = QuoteCurrency(symbol="USDC", name="USD Coin", active=True)
    db_session.add_all([usd, usdc])

    # Create market types
    perps = MarketType(name="perps", display_name="Perpetuals", active=True)
    spot = MarketType(name="spot", display_name="Spot", active=True)
    db_session.add_all([perps, spot])

    # Create intervals
    intervals_data = [
        ("1m", 60),
        ("15m", 900),
        ("4h", 14400),
        ("1d", 86400),
    ]
    intervals = [
        Interval(name=name, seconds=seconds, active=True)
        for name, seconds in intervals_data
    ]
    db_session.add_all(intervals)

    await db_session.commit()
    await db_session.refresh(exchange)
    await db_session.refresh(btc)
    await db_session.refresh(sol)
    await db_session.refresh(usd)
    await db_session.refresh(usdc)
    await db_session.refresh(perps)
    await db_session.refresh(spot)
    for interval in intervals:
        await db_session.refresh(interval)

    return {
        "exchange": exchange,
        "btc": btc,
        "sol": sol,
        "usd": usd,
        "usdc": usdc,
        "perps": perps,
        "spot": spot,
        "intervals": {interval.name: interval for interval in intervals},
    }


@pytest_asyncio.fixture(scope="function")
async def seed_starlistings(
    db_session: AsyncSession,
    seed_base_data: dict[str, Any],
) -> list[Starlisting]:
    """Seed database with test starlistings."""
    from src.db.models import TradingPair

    exchange = seed_base_data["exchange"]
    btc = seed_base_data["btc"]
    sol = seed_base_data["sol"]
    usd = seed_base_data["usd"]
    perps = seed_base_data["perps"]
    intervals = seed_base_data["intervals"]

    # First, create trading pairs
    # BTC/USD perps trading pair
    btc_usd_perps = TradingPair(
        exchange_id=exchange.id,
        coin_id=btc.id,
        quote_currency_id=usd.id,
        market_type_id=perps.id,
    )
    db_session.add(btc_usd_perps)

    # SOL/USD perps trading pair
    sol_usd_perps = TradingPair(
        exchange_id=exchange.id,
        coin_id=sol.id,
        quote_currency_id=usd.id,
        market_type_id=perps.id,
    )
    db_session.add(sol_usd_perps)

    await db_session.commit()
    await db_session.refresh(btc_usd_perps)
    await db_session.refresh(sol_usd_perps)

    starlistings = []

    # BTC/USD perps - all intervals
    for interval_name in ["1m", "15m", "4h", "1d"]:
        starlisting = Starlisting(
            exchange_id=exchange.id,
            coin_id=btc.id,
            quote_currency_id=usd.id,
            market_type_id=perps.id,
            interval_id=intervals[interval_name].id,
            trading_pair_id=btc_usd_perps.id,
            active=True,
        )
        db_session.add(starlisting)
        starlistings.append(starlisting)

    # SOL/USD perps - 1m and 4h only
    for interval_name in ["1m", "4h"]:
        starlisting = Starlisting(
            exchange_id=exchange.id,
            coin_id=sol.id,
            quote_currency_id=usd.id,
            market_type_id=perps.id,
            interval_id=intervals[interval_name].id,
            trading_pair_id=sol_usd_perps.id,
            active=True,
        )
        db_session.add(starlisting)
        starlistings.append(starlisting)

    await db_session.commit()
    for starlisting in starlistings:
        await db_session.refresh(starlisting)

    return starlistings


@pytest.fixture
def test_client(db_session: AsyncSession):
    """Create a test client for the FastAPI app."""
    # Override the database dependency
    from src.api.dependencies import get_db_session

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    # Use TestClient without running lifespan
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    from src.api.dependencies import get_db_session

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
