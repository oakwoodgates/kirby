"""
Sync training_stars.yaml configuration to the training database.

This script reads config/training_stars.yaml and syncs it to the kirby_training database,
creating or updating exchanges, coins, quote_currencies, market_types, intervals, and training_stars.

Usage:
    python -m scripts.sync_training_config

    # Or in Docker:
    docker compose exec collector python -m scripts.sync_training_config
"""
import asyncio
from pathlib import Path

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.db.base import Base
from src.db.connection import close_db, get_session, init_db
from src.db.models import Coin, Exchange, Interval, MarketType, QuoteCurrency, Starlisting
from src.utils.logging import setup_logging

logger = structlog.get_logger("kirby.scripts.sync_training_config")


class TrainingConfigSyncer:
    """Syncs training_stars.yaml configuration to the training database."""

    def __init__(self, config_path: Path):
        """Initialize the config syncer.

        Args:
            config_path: Path to training_stars.yaml
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load training_stars.yaml configuration.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config is invalid YAML
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path) as f:
            config = yaml.safe_load(f)

        logger.info("Loaded training config", path=str(self.config_path))
        return config

    async def sync_exchanges(self, session: AsyncSession) -> dict[str, Exchange]:
        """Sync exchanges to database.

        Args:
            session: Database session

        Returns:
            Dictionary mapping exchange name to Exchange model
        """
        exchanges = {}

        for exc_config in self.config.get("exchanges", []):
            name = exc_config["name"]

            # Check if exchange exists
            result = await session.execute(
                select(Exchange).where(Exchange.name == name)
            )
            exchange = result.scalar_one_or_none()

            if exchange:
                # Update existing
                exchange.display_name = exc_config.get("display_name", name.title())
                exchange.active = exc_config.get("active", True)
                logger.info("Updated exchange", name=name)
            else:
                # Create new
                exchange = Exchange(
                    name=name,
                    display_name=exc_config.get("display_name", name.title()),
                    active=exc_config.get("active", True),
                )
                session.add(exchange)
                logger.info("Created exchange", name=name)

            exchanges[name] = exchange

        await session.commit()
        logger.info("Synced exchanges", count=len(exchanges))
        return exchanges

    async def sync_coins(self, session: AsyncSession) -> dict[str, Coin]:
        """Sync coins to database.

        Args:
            session: Database session

        Returns:
            Dictionary mapping coin symbol to Coin model
        """
        coins = {}

        for coin_config in self.config.get("coins", []):
            symbol = coin_config["symbol"]

            # Check if coin exists
            result = await session.execute(
                select(Coin).where(Coin.symbol == symbol)
            )
            coin = result.scalar_one_or_none()

            if coin:
                # Update existing
                coin.name = coin_config.get("name", symbol)
                coin.active = coin_config.get("active", True)
                logger.info("Updated coin", symbol=symbol)
            else:
                # Create new
                coin = Coin(
                    symbol=symbol,
                    name=coin_config.get("name", symbol),
                    active=coin_config.get("active", True),
                )
                session.add(coin)
                logger.info("Created coin", symbol=symbol)

            coins[symbol] = coin

        await session.commit()
        logger.info("Synced coins", count=len(coins))
        return coins

    async def sync_quote_currencies(self, session: AsyncSession) -> dict[str, QuoteCurrency]:
        """Sync quote currencies to database.

        Args:
            session: Database session

        Returns:
            Dictionary mapping quote symbol to QuoteCurrency model
        """
        quotes = {}

        for quote_config in self.config.get("quote_currencies", []):
            symbol = quote_config["symbol"]

            # Check if quote exists
            result = await session.execute(
                select(QuoteCurrency).where(QuoteCurrency.symbol == symbol)
            )
            quote = result.scalar_one_or_none()

            if quote:
                # Update existing
                quote.name = quote_config.get("name", symbol)
                quote.active = quote_config.get("active", True)
                logger.info("Updated quote currency", symbol=symbol)
            else:
                # Create new
                quote = QuoteCurrency(
                    symbol=symbol,
                    name=quote_config.get("name", symbol),
                    active=quote_config.get("active", True),
                )
                session.add(quote)
                logger.info("Created quote currency", symbol=symbol)

            quotes[symbol] = quote

        await session.commit()
        logger.info("Synced quote currencies", count=len(quotes))
        return quotes

    async def sync_market_types(self, session: AsyncSession) -> dict[str, MarketType]:
        """Sync market types to database.

        Args:
            session: Database session

        Returns:
            Dictionary mapping market type name to MarketType model
        """
        market_types = {}

        for mt_config in self.config.get("market_types", []):
            name = mt_config["name"]

            # Check if market type exists
            result = await session.execute(
                select(MarketType).where(MarketType.name == name)
            )
            market_type = result.scalar_one_or_none()

            if market_type:
                # Update existing
                market_type.display_name = mt_config.get("display_name", name.title())
                market_type.active = mt_config.get("active", True)
                logger.info("Updated market type", name=name)
            else:
                # Create new
                market_type = MarketType(
                    name=name,
                    display_name=mt_config.get("display_name", name.title()),
                    active=mt_config.get("active", True),
                )
                session.add(market_type)
                logger.info("Created market type", name=name)

            market_types[name] = market_type

        await session.commit()
        logger.info("Synced market types", count=len(market_types))
        return market_types

    async def sync_intervals(self, session: AsyncSession) -> dict[str, Interval]:
        """Sync intervals to database.

        Args:
            session: Database session

        Returns:
            Dictionary mapping interval name to Interval model
        """
        intervals = {}

        for interval_config in self.config.get("intervals", []):
            name = interval_config["name"]

            # Check if interval exists
            result = await session.execute(
                select(Interval).where(Interval.name == name)
            )
            interval = result.scalar_one_or_none()

            if interval:
                # Update existing
                interval.seconds = interval_config["seconds"]
                interval.active = interval_config.get("active", True)
                logger.info("Updated interval", name=name)
            else:
                # Create new
                interval = Interval(
                    name=name,
                    seconds=interval_config["seconds"],
                    active=interval_config.get("active", True),
                )
                session.add(interval)
                logger.info("Created interval", name=name)

            intervals[name] = interval

        await session.commit()
        logger.info("Synced intervals", count=len(intervals))
        return intervals

    async def sync_training_stars(
        self,
        session: AsyncSession,
        exchanges: dict[str, Exchange],
        coins: dict[str, Coin],
        quotes: dict[str, QuoteCurrency],
        market_types: dict[str, MarketType],
        intervals: dict[str, Interval],
    ) -> int:
        """Sync training stars to database.

        Args:
            session: Database session
            exchanges: Dictionary of exchanges
            coins: Dictionary of coins
            quotes: Dictionary of quote currencies
            market_types: Dictionary of market types
            intervals: Dictionary of intervals

        Returns:
            Number of training stars synced
        """
        count = 0

        for star_config in self.config.get("training_stars", []):
            exchange_name = star_config["exchange"]
            coin_symbol = star_config["coin"]
            quote_symbol = star_config["quote"]
            market_type_name = star_config["market_type"]
            interval_names = star_config["intervals"]
            active = star_config.get("active", True)

            # Get reference objects
            exchange = exchanges.get(exchange_name)
            coin = coins.get(coin_symbol)
            quote = quotes.get(quote_symbol)
            market_type = market_types.get(market_type_name)

            if not all([exchange, coin, quote, market_type]):
                logger.warning(
                    "Skipping training star - missing reference",
                    exchange=exchange_name,
                    coin=coin_symbol,
                    quote=quote_symbol,
                    market_type=market_type_name,
                )
                continue

            # Create starlisting for each interval
            for interval_name in interval_names:
                interval = intervals.get(interval_name)
                if not interval:
                    logger.warning(
                        "Skipping interval - not found",
                        interval=interval_name,
                    )
                    continue

                # Check if starlisting exists
                result = await session.execute(
                    select(Starlisting).where(
                        Starlisting.exchange_id == exchange.id,
                        Starlisting.coin_id == coin.id,
                        Starlisting.quote_currency_id == quote.id,
                        Starlisting.market_type_id == market_type.id,
                        Starlisting.interval_id == interval.id,
                    )
                )
                starlisting = result.scalar_one_or_none()

                if starlisting:
                    # Update existing
                    starlisting.active = active
                    logger.info(
                        "Updated training star",
                        exchange=exchange_name,
                        coin=coin_symbol,
                        quote=quote_symbol,
                        market_type=market_type_name,
                        interval=interval_name,
                    )
                else:
                    # Create new
                    starlisting = Starlisting(
                        exchange_id=exchange.id,
                        coin_id=coin.id,
                        quote_currency_id=quote.id,
                        market_type_id=market_type.id,
                        interval_id=interval.id,
                        active=active,
                    )
                    session.add(starlisting)
                    logger.info(
                        "Created training star",
                        exchange=exchange_name,
                        coin=coin_symbol,
                        quote=quote_symbol,
                        market_type=market_type_name,
                        interval=interval_name,
                    )

                count += 1

        await session.commit()
        logger.info("Synced training stars", count=count)
        return count

    async def sync(self, session: AsyncSession) -> None:
        """Sync all configuration to database.

        Args:
            session: Database session
        """
        logger.info("Starting training config sync")

        # Sync reference tables first
        exchanges = await self.sync_exchanges(session)
        coins = await self.sync_coins(session)
        quotes = await self.sync_quote_currencies(session)
        market_types = await self.sync_market_types(session)
        intervals = await self.sync_intervals(session)

        # Sync training stars
        count = await self.sync_training_stars(
            session, exchanges, coins, quotes, market_types, intervals
        )

        logger.info("Training config sync complete", training_stars=count)


async def main() -> None:
    """Main entry point."""
    # Set up logging
    setup_logging()
    logger.info("Starting training config sync script")

    # Get training database URL from environment
    settings = Settings()
    training_db_url = getattr(settings, "training_database_url", None)

    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in environment")
        logger.info("Please add TRAINING_DATABASE_URL to your .env file")
        return

    logger.info("Using training database", url=str(training_db_url))

    # Initialize database with training URL
    await init_db(database_url=str(training_db_url))

    try:
        # Load config
        config_path = Path("config/training_stars.yaml")
        syncer = TrainingConfigSyncer(config_path)

        # Get session
        session = await get_session(database_url=str(training_db_url))

        try:
            # Sync configuration
            await syncer.sync(session)
        finally:
            await session.close()

        logger.info("Training config sync completed successfully")

    except Exception as e:
        logger.error("Training config sync failed", error=str(e), exc_info=True)
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
