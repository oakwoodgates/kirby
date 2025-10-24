"""
Seed database with initial exchanges, coins, listing types, and listings.

Run this script to set up the initial data before starting collectors.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session, init_db
from src.models import Coin, Exchange, Listing, ListingType
from src.models.listing import BackfillStatus
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def seed_exchanges(session: AsyncSession) -> dict[str, int]:
    """
    Seed exchanges table.

    Returns:
        Dictionary mapping exchange names to their IDs
    """
    logger.info("Seeding exchanges...")

    exchanges_data = [
        {
            "name": "hyperliquid",
            "ccxt_id": "hyperliquid",
            "is_ccxt_supported": True,
            "custom_integration_class": None,
            "exchange_metadata": {
                "rate_limits": {"requests_per_second": 10},
                "capabilities": ["spot", "perpetuals"],
            },
        },
        {
            "name": "binance",
            "ccxt_id": "binance",
            "is_ccxt_supported": True,
            "custom_integration_class": None,
            "exchange_metadata": {
                "rate_limits": {"requests_per_second": 20},
                "capabilities": ["spot", "futures", "options"],
            },
        },
        {
            "name": "coinbase",
            "ccxt_id": "coinbase",
            "is_ccxt_supported": True,
            "custom_integration_class": None,
            "exchange_metadata": {
                "rate_limits": {"requests_per_second": 5},
                "capabilities": ["spot"],
            },
        },
    ]

    exchange_ids = {}
    for ex_data in exchanges_data:
        # Check if exchange exists
        result = await session.execute(
            select(Exchange).where(Exchange.name == ex_data["name"])
        )
        exchange = result.scalar_one_or_none()

        if exchange:
            logger.info(f"Exchange '{ex_data['name']}' already exists (ID: {exchange.id})")
            exchange_ids[ex_data["name"]] = exchange.id
        else:
            exchange = Exchange(**ex_data)
            session.add(exchange)
            await session.flush()
            exchange_ids[ex_data["name"]] = exchange.id
            logger.info(f"Created exchange '{ex_data['name']}' (ID: {exchange.id})")

    await session.commit()
    return exchange_ids


async def seed_coins(session: AsyncSession) -> dict[str, int]:
    """
    Seed coins table.

    Returns:
        Dictionary mapping coin symbols to their IDs
    """
    logger.info("Seeding coins...")

    coins_data = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "coin_metadata": {
                "coingecko_id": "bitcoin",
                "coinmarketcap_id": "1",
            },
        },
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "coin_metadata": {
                "coingecko_id": "ethereum",
                "coinmarketcap_id": "1027",
            },
        },
        {
            "symbol": "HYPE",
            "name": "Hyperliquid",
            "coin_metadata": {
                "network": "Hyperliquid L1",
            },
        },
    ]

    coin_ids = {}
    for coin_data in coins_data:
        # Check if coin exists
        result = await session.execute(
            select(Coin).where(Coin.symbol == coin_data["symbol"])
        )
        coin = result.scalar_one_or_none()

        if coin:
            logger.info(f"Coin '{coin_data['symbol']}' already exists (ID: {coin.id})")
            coin_ids[coin_data["symbol"]] = coin.id
        else:
            coin = Coin(**coin_data)
            session.add(coin)
            await session.flush()
            coin_ids[coin_data["symbol"]] = coin.id
            logger.info(f"Created coin '{coin_data['symbol']}' (ID: {coin.id})")

    await session.commit()
    return coin_ids


async def seed_listing_types(session: AsyncSession) -> dict[str, int]:
    """
    Seed listing_type table.

    Returns:
        Dictionary mapping listing type names to their IDs
    """
    logger.info("Seeding listing types...")

    types_data = [
        {
            "type": "perps",
            "description": "Perpetual futures (no expiry, funding rate mechanism)",
        },
        {
            "type": "futures",
            "description": "Dated futures contracts with expiration",
        },
        {
            "type": "spot",
            "description": "Spot trading (immediate exchange)",
        },
        {
            "type": "options",
            "description": "Options contracts (calls and puts)",
        },
    ]

    type_ids = {}
    for type_data in types_data:
        # Check if type exists
        result = await session.execute(
            select(ListingType).where(ListingType.type == type_data["type"])
        )
        listing_type = result.scalar_one_or_none()

        if listing_type:
            logger.info(f"Listing type '{type_data['type']}' already exists (ID: {listing_type.id})")
            type_ids[type_data["type"]] = listing_type.id
        else:
            listing_type = ListingType(**type_data)
            session.add(listing_type)
            await session.flush()
            type_ids[type_data["type"]] = listing_type.id
            logger.info(f"Created listing type '{type_data['type']}' (ID: {listing_type.id})")

    await session.commit()
    return type_ids


async def seed_listings(
    session: AsyncSession,
    exchange_ids: dict[str, int],
    coin_ids: dict[str, int],
    type_ids: dict[str, int],
) -> list[Listing]:
    """
    Seed listings table with initial trading pairs.

    Returns:
        List of created Listing objects
    """
    logger.info("Seeding listings...")

    listings_data = [
        {
            "exchange": "hyperliquid",
            "coin": "BTC",
            "type": "perps",
            "ccxt_symbol": "BTC/USDC:USDC",
            "is_active": True,
            "collector_config": {
                "type": "websocket",
                "coin_name": "BTC",
                "channels": ["candle", "l2Book", "activeAssetCtx"],
                "candle_interval": "1m",
                "fallback_to_polling": True,
            },
        },
        {
            "exchange": "hyperliquid",
            "coin": "HYPE",
            "type": "perps",
            "ccxt_symbol": "HYPE/USDC:USDC",
            "is_active": True,
            "collector_config": {
                "type": "websocket",
                "coin_name": "HYPE",
                "channels": ["candle", "l2Book", "activeAssetCtx"],
                "candle_interval": "1m",
                "fallback_to_polling": True,
            },
        },
    ]

    listings = []
    for listing_data in listings_data:
        exchange_id = exchange_ids[listing_data["exchange"]]
        coin_id = coin_ids[listing_data["coin"]]
        type_id = type_ids[listing_data["type"]]

        # Check if listing exists
        result = await session.execute(
            select(Listing).where(
                Listing.exchange_id == exchange_id,
                Listing.coin_id == coin_id,
                Listing.listing_type_id == type_id,
            )
        )
        listing = result.scalar_one_or_none()

        if listing:
            logger.info(
                f"Listing '{listing_data['exchange']}/{listing_data['coin']}/{listing_data['type']}' "
                f"already exists (ID: {listing.id})"
            )
            listings.append(listing)
        else:
            listing = Listing(
                exchange_id=exchange_id,
                coin_id=coin_id,
                listing_type_id=type_id,
                ccxt_symbol=listing_data["ccxt_symbol"],
                is_active=listing_data["is_active"],
                backfill_status=BackfillStatus.PENDING,
                backfill_progress=None,
                collector_config=listing_data["collector_config"],
                listing_metadata=None,
                activated_at=datetime.now(timezone.utc) if listing_data["is_active"] else None,
            )
            session.add(listing)
            await session.flush()
            listings.append(listing)
            logger.info(
                f"Created listing '{listing_data['exchange']}/{listing_data['coin']}/{listing_data['type']}' "
                f"(ID: {listing.id}, Symbol: {listing_data['ccxt_symbol']})"
            )

    await session.commit()
    return listings


async def main():
    """
    Main seeding function.
    """
    setup_logging(log_level="INFO", log_format="text")
    logger.info("=== Starting database seeding ===")

    # Initialize database (synchronous)
    init_db()

    async with get_session() as session:
        try:
            # Seed in order (respecting foreign keys)
            exchange_ids = await seed_exchanges(session)
            coin_ids = await seed_coins(session)
            type_ids = await seed_listing_types(session)
            listings = await seed_listings(session, exchange_ids, coin_ids, type_ids)

            logger.info("\n=== Seeding Summary ===")
            logger.info(f"Exchanges: {len(exchange_ids)}")
            logger.info(f"Coins: {len(coin_ids)}")
            logger.info(f"Listing Types: {len(type_ids)}")
            logger.info(f"Listings: {len(listings)}")

            logger.info("\n=== Active Listings ===")
            for listing in listings:
                if listing.is_active:
                    logger.info(
                        f"ID {listing.id}: {listing.ccxt_symbol} "
                        f"(Exchange ID: {listing.exchange_id}, Coin ID: {listing.coin_id})"
                    )

            logger.info("\n=== Database seeding complete! ===")

        except Exception as e:
            logger.error(f"Error during seeding: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
