"""
Set up training database in one command.

This script automates the complete setup of the training database:
1. Creates kirby_training database (if it doesn't exist)
2. Enables TimescaleDB extension
3. Runs Alembic migrations to create tables
4. Syncs training_stars.yaml configuration

Usage:
    python -m scripts.setup_training_db

    # Or in Docker:
    docker compose exec collector python -m scripts.setup_training_db
"""
import asyncio
import subprocess
import sys

import asyncpg
import structlog

from src.config.settings import Settings
from src.utils.logging import setup_logging

logger = structlog.get_logger("kirby.scripts.setup_training_db")


async def create_database(db_name: str, connection_string: str) -> bool:
    """Create training database if it doesn't exist.

    Args:
        db_name: Database name (e.g., kirby_training)
        connection_string: PostgreSQL connection string

    Returns:
        True if database was created or already exists
    """
    try:
        # Connect to postgres database
        postgres_url = connection_string.replace(f"/{db_name}", "/postgres")
        postgres_url = postgres_url.replace("+asyncpg", "")  # Use pure asyncpg

        # Extract host info for logging (hide password)
        url_parts = postgres_url.split("@")
        host_info = url_parts[1] if len(url_parts) > 1 else "unknown"
        logger.info("Connecting to PostgreSQL", host=host_info)

        conn = await asyncpg.connect(postgres_url)

        try:
            # Check if database exists
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )

            if result:
                logger.info("Database already exists", database=db_name)
                return True

            # Create database
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info("Created database", database=db_name)
            return True

        finally:
            await conn.close()

    except Exception as e:
        logger.error("Failed to create database", error=str(e), exc_info=True)
        return False


async def enable_timescaledb(database_url: str) -> bool:
    """Enable TimescaleDB extension.

    Args:
        database_url: Training database URL

    Returns:
        True if extension was enabled
    """
    try:
        # Use asyncpg directly since we're connecting to a custom database
        # Convert SQLAlchemy URL format to asyncpg format
        asyncpg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        conn = await asyncpg.connect(asyncpg_url)
        try:
            # Enable TimescaleDB extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            logger.info("Enabled TimescaleDB extension")
            return True

        finally:
            await conn.close()

    except Exception as e:
        logger.error("Failed to enable TimescaleDB", error=str(e), exc_info=True)
        return False


async def run_migrations(database_url: str) -> bool:
    """Run Alembic migrations on training database.

    Args:
        database_url: Training database URL

    Returns:
        True if migrations succeeded
    """
    try:
        logger.info("Running database migrations...")

        # Set DATABASE_URL env var and run alembic
        import os
        env = os.environ.copy()
        env["DATABASE_URL"] = database_url

        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Ran migrations successfully")
            # Show alembic output
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        logger.debug("alembic", message=line.strip())
            return True
        else:
            logger.error("Migration failed", stderr=result.stderr)
            return False

    except Exception as e:
        logger.error("Failed to run migrations", error=str(e), exc_info=True)
        return False


async def sync_config() -> bool:
    """Sync training_stars.yaml configuration to database.

    Returns:
        True if sync succeeded
    """
    try:
        logger.info("Syncing training_stars.yaml configuration...")

        result = subprocess.run(
            [sys.executable, "-m", "scripts.sync_training_config"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Configuration sync successful")
            return True
        else:
            logger.error("Config sync failed", stderr=result.stderr)
            # Show stdout for debugging
            if result.stdout:
                logger.debug("sync output", output=result.stdout)
            return False

    except Exception as e:
        logger.error("Failed to sync config", error=str(e), exc_info=True)
        return False


async def main() -> None:
    """Main entry point."""
    setup_logging()

    print("=" * 60)
    print("  Training Database Setup")
    print("=" * 60)
    print()

    logger.info("Starting training database setup")

    # Get training database URL
    settings = Settings()
    training_db_url = settings.training_database_url
    training_db_name = settings.training_db

    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in .env")
        print()
        print("ERROR: TRAINING_DATABASE_URL not configured!")
        print()
        print("Please add the following to your .env file:")
        print()
        print(f"  TRAINING_DB={training_db_name}")
        print(f"  TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/{training_db_name}")
        print("  TRAINING_DATABASE_POOL_SIZE=10")
        print()
        sys.exit(1)

    training_db_url_str = str(training_db_url)
    logger.info("Target database", name=training_db_name, url=training_db_url_str.split("@")[1])

    print(f"Setting up: {training_db_name}")
    print()

    # Step 1: Create database
    print("Step 1/4: Creating database...")
    if not await create_database(training_db_name, training_db_url_str):
        print("  ❌ Failed to create database")
        sys.exit(1)
    print("  ✓ Database ready")
    print()

    # Step 2: Enable TimescaleDB
    print("Step 2/4: Enabling TimescaleDB extension...")
    if not await enable_timescaledb(training_db_url_str):
        print("  ❌ Failed to enable TimescaleDB")
        sys.exit(1)
    print("  ✓ TimescaleDB enabled")
    print()

    # Step 3: Run migrations
    print("Step 3/4: Running database migrations...")
    if not await run_migrations(training_db_url_str):
        print("  ❌ Failed to run migrations")
        sys.exit(1)
    print("  ✓ Tables created")
    print()

    # Step 4: Sync configuration
    print("Step 4/4: Syncing training_stars.yaml...")
    if not await sync_config():
        print("  ❌ Failed to sync configuration")
        sys.exit(1)
    print("  ✓ Configuration synced")
    print()

    print("=" * 60)
    print("  Setup Complete! ✓")
    print("=" * 60)
    print()
    print("Next steps:")
    print()
    print("  1. Review config/training_stars.yaml")
    print("     Edit to add/remove exchanges, coins, intervals")
    print()
    print("  2. Backfill historical data:")
    print(f"     python -m scripts.backfill_training --days=365")
    print()
    print("  3. Export data for ML:")
    print("     python -m scripts.export_all --database=training --format=parquet")
    print()
    print("Documentation: docs/TRAINING_STARS.md")
    print()


if __name__ == "__main__":
    asyncio.run(main())
