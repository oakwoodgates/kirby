"""
Sync configuration from YAML to database.

Usage:
    python -m scripts.sync_config
    python -m scripts.sync_config --config=path/to/config.yaml
"""
import argparse
import asyncio
import sys
from pathlib import Path

import structlog

from src.config.loader import ConfigLoader
from src.db.connection import close_db, get_session, init_db
from src.utils.logging import setup_logging


async def sync_config(config_path: str) -> None:
    """
    Sync configuration from YAML to database.

    Args:
        config_path: Path to configuration YAML file
    """
    logger = structlog.get_logger("kirby.scripts.sync_config")

    try:
        # Initialize database
        logger.info("Initializing database connection")
        await init_db()

        # Load and sync configuration
        logger.info("Loading configuration", config_path=config_path)
        config_loader = ConfigLoader(config_path)

        async with get_session() as session:
            await config_loader.sync_to_database(session)

        logger.info("Configuration synced successfully")

    except FileNotFoundError as e:
        logger.error(
            "Configuration file not found",
            config_path=config_path,
            error=str(e),
        )
        sys.exit(1)
    except Exception as e:
        logger.error(
            "Failed to sync configuration",
            error=str(e),
            exc_info=True,
        )
        sys.exit(1)
    finally:
        await close_db()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync Kirby configuration from YAML to database"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/starlistings.yaml",
        help="Path to configuration YAML file (default: config/starlistings.yaml)",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging()

    # Run sync
    asyncio.run(sync_config(args.config))


if __name__ == "__main__":
    main()
