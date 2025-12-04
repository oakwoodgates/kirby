"""
Configuration loader to sync YAML config to database.
"""
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import (
    CoinRepository,
    ExchangeRepository,
    IntervalRepository,
    MarketTypeRepository,
    QuoteCurrencyRepository,
    StarlistingRepository,
)

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads configuration from YAML and syncs to database."""

    def __init__(self, config_path: str | Path = "config/starlistings.yaml"):
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}

    def load_yaml(self) -> dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        logger.info(f"Loaded config from {self.config_path}")
        return self.config

    async def sync_to_database(self, session: AsyncSession) -> None:
        """
        Sync configuration to database.

        This will:
        1. Create or update exchanges, coins, and market types
        2. Create starlistings for each combination
        """
        if not self.config:
            self.load_yaml()

        # Initialize repositories
        exchange_repo = ExchangeRepository(session)
        coin_repo = CoinRepository(session)
        quote_currency_repo = QuoteCurrencyRepository(session)
        market_type_repo = MarketTypeRepository(session)
        interval_repo = IntervalRepository(session)
        starlisting_repo = StarlistingRepository(session)

        # Sync exchanges
        logger.info("Syncing exchanges...")
        exchanges = {}
        for exchange_data in self.config.get("exchanges", []):
            exchange = await exchange_repo.get_or_create(
                name=exchange_data["name"],
                display_name=exchange_data["display_name"],
            )
            exchanges[exchange.name] = exchange
            logger.info(f"  - {exchange.name}")

        # Sync coins
        logger.info("Syncing coins...")
        coins = {}
        for coin_data in self.config.get("coins", []):
            coin = await coin_repo.get_or_create(
                symbol=coin_data["symbol"],
                name=coin_data["name"],
            )
            coins[coin.symbol] = coin
            logger.info(f"  - {coin.symbol}")

        # Sync quote currencies
        logger.info("Syncing quote currencies...")
        quote_currencies = {}
        for quote_data in self.config.get("quote_currencies", []):
            quote = await quote_currency_repo.get_or_create(
                symbol=quote_data["symbol"],
                name=quote_data["name"],
            )
            quote_currencies[quote.symbol] = quote
            logger.info(f"  - {quote.symbol}")

        # Sync market types
        logger.info("Syncing market types...")
        market_types = {}
        for market_type_data in self.config.get("market_types", []):
            market_type = await market_type_repo.get_or_create(
                name=market_type_data["name"],
                display_name=market_type_data["display_name"],
            )
            market_types[market_type.name] = market_type
            logger.info(f"  - {market_type.name}")

        # Sync starlistings
        logger.info("Syncing starlistings...")
        starlisting_count = 0

        for starlisting_data in self.config.get("starlistings", []):
            exchange_name = starlisting_data["exchange"]
            coin_symbol = starlisting_data["coin"]
            quote_symbol = starlisting_data["quote"]
            market_type_name = starlisting_data["market_type"]
            intervals = starlisting_data["intervals"]
            active = starlisting_data.get("active", True)

            # Get the related objects
            exchange = exchanges.get(exchange_name)
            coin = coins.get(coin_symbol)
            quote = quote_currencies.get(quote_symbol)
            market_type = market_types.get(market_type_name)

            if not exchange or not coin or not quote or not market_type:
                logger.warning(
                    f"Skipping starlisting {exchange_name}/{coin_symbol}/{quote_symbol}/{market_type_name}: "
                    f"Missing reference"
                )
                continue

            # Create starlistings for each interval
            for interval_name in intervals:
                interval = await interval_repo.get_by_name(interval_name)
                if not interval:
                    logger.warning(
                        f"Interval '{interval_name}' not found in database. Skipping."
                    )
                    continue

                # Check if starlisting already exists
                existing = await starlisting_repo.get_by_components(
                    exchange_id=exchange.id,
                    coin_id=coin.id,
                    quote_currency_id=quote.id,
                    market_type_id=market_type.id,
                    interval_id=interval.id,
                )

                if existing:
                    # Update active status if changed
                    if existing.active != active:
                        await starlisting_repo.update(existing.id, active=active)
                        logger.info(
                            f"  - Updated: {exchange_name}/{coin_symbol}/{quote_symbol}/{market_type_name} "
                            f"{interval_name} (active={active})"
                        )
                else:
                    # Create new starlisting
                    await starlisting_repo.create(
                        exchange_id=exchange.id,
                        coin_id=coin.id,
                        quote_currency_id=quote.id,
                        market_type_id=market_type.id,
                        interval_id=interval.id,
                        active=active,
                    )
                    logger.info(
                        f"  - Created: {exchange_name}/{coin_symbol}/{quote_symbol}/{market_type_name} "
                        f"{interval_name}"
                    )
                    starlisting_count += 1

        await session.commit()
        logger.info(f"Synced {starlisting_count} starlistings to database")

    async def get_active_starlistings(self, session: AsyncSession) -> list[dict[str, Any]]:
        """
        Get all active starlistings from database.

        Returns:
            List of starlisting dictionaries with all related data.
        """
        starlisting_repo = StarlistingRepository(session)
        starlistings = await starlisting_repo.get_active_starlistings()

        result = []
        for starlisting in starlistings:
            result.append(
                {
                    "id": starlisting.id,
                    "exchange": starlisting.exchange.name,
                    "exchange_display": starlisting.exchange.display_name,
                    "coin": starlisting.coin.symbol,
                    "coin_name": starlisting.coin.name,
                    "quote": starlisting.quote_currency.symbol,
                    "quote_name": starlisting.quote_currency.name,
                    "trading_pair": starlisting.get_trading_pair(),
                    "trading_pair_id": starlisting.trading_pair_id,
                    "market_type": starlisting.market_type.name,
                    "market_type_display": starlisting.market_type.display_name,
                    "interval": starlisting.interval.name,
                    "interval_seconds": starlisting.interval.seconds,
                }
            )

        return result
