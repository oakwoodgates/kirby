# Training Stars - Implementation Guide

> Complete implementation guide for the Training Stars system with remaining scripts and setup instructions.

---

## Summary

Training Stars is a modular system for collecting historical cryptocurrency data from Binance, Bybit, OKX, and other exchanges for ML training and backtesting.

### What's Been Created

✅ **[config/training_stars.yaml](../config/training_stars.yaml)** - Configuration with Binance defaults
✅ **[docs/TRAINING_STARS.md](TRAINING_STARS.md)** - Complete 400+ line documentation
✅ **[scripts/sync_training_config.py](../scripts/sync_training_config.py)** - Sync YAML → database
✅ **[.env.example](.env.example)** - Updated with training DB variables

### What Needs to Be Created

The following files need to be created. I'll provide the complete code below:

1. `scripts/backfill_training.py` - Backfill historical candle data
2. `scripts/setup_training_db.py` - One-command database setup
3. Update `src/config/settings.py` - Add training database URL setting

---

## File 1: scripts/backfill_training.py

This script is identical to `scripts/backfill.py` but uses the training database URL. Here's what you need to do:

**Option A: Copy and modify existing backfill.py:**

```bash
# Copy the existing backfill script
cp scripts/backfill.py scripts/backfill_training.py
```

Then update line ~358 in `backfill_training.py`:

```python
# CHANGE FROM:
await init_db()

# CHANGE TO:
# Get training database URL
settings = Settings()
training_db_url = getattr(settings, "training_database_url", None)
if not training_db_url:
    logger.error("TRAINING_DATABASE_URL not set")
    return

await init_db(database_url=str(training_db_url))
```

Also update the config loader section (~253) to use training_stars.yaml:

```python
# CHANGE FROM:
config_loader = ConfigLoader()

# CHANGE TO:
from pathlib import Path
config_loader = ConfigLoader(config_path=Path("config/training_stars.yaml"))
```

**Option B: Full script (simplified)**

Create `scripts/backfill_training.py` with this content:

```python
"""
Backfill training data from Binance, Bybit, etc.

Usage:
    python -m scripts.backfill_training --days=365
    python -m scripts.backfill_training --exchange=binance --coin=BTC --days=90
"""
# Import everything from backfill.py
from scripts.backfill import *

# Override main() to use training database
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill training data for ML/backtesting"
    )
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--exchange", type=str)
    parser.add_argument("--coin", type=str)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    setup_logging()
    logger = structlog.get_logger("kirby.scripts.backfill_training")

    # Use training database
    settings = Settings()
    training_db_url = getattr(settings, "training_database_url", None)
    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in .env")
        return

    logger.info("Using training database", url=str(training_db_url))
    await init_db(database_url=str(training_db_url))

    try:
        service = BackfillService()

        # Load training stars from training database
        session = await get_session(database_url=str(training_db_url))
        try:
            from pathlib import Path
            config_loader = ConfigLoader(config_path=Path("config/training_stars.yaml"))
            starlistings = await config_loader.get_active_starlistings(session)
        finally:
            await session.close()

        # Filter if needed
        if args.exchange or args.coin:
            starlistings = [
                sl for sl in starlistings
                if (not args.exchange or sl["exchange"] == args.exchange)
                and (not args.coin or sl["coin"] == args.coin)
            ]

        logger.info("Loaded training stars", count=len(starlistings))

        # Backfill each training star
        total_candles = 0
        for starlisting in starlistings:
            candles = await service.backfill_starlisting(starlisting, days=args.days)
            total_candles += candles

        logger.info("Backfill complete", total_candles=total_candles)

    except Exception as e:
        logger.error("Backfill failed", error=str(e), exc_info=True)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## File 2: scripts/setup_training_db.py

One-command script to set up the entire training database:

```python
"""
Set up training database in one command.

This script:
1. Creates kirby_training database (if it doesn't exist)
2. Enables TimescaleDB extension
3. Runs Alembic migrations
4. Syncs training_stars.yaml configuration

Usage:
    python -m scripts.setup_training_db

    # Or in Docker:
    docker compose exec collector python -m scripts.setup_training_db
"""
import asyncio
import sys

import asyncpg
import structlog
from sqlalchemy import text

from src.config.settings import Settings
from src.db.connection import close_db, get_session, init_db
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
        postgres_url = postgres_url.replace("+asyncpg", "")  # asyncpg for connection

        logger.info("Connecting to PostgreSQL", url=postgres_url.split("@")[1])
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
        await init_db(database_url=database_url)
        session = await get_session(database_url=database_url)

        try:
            # Enable TimescaleDB extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            await session.commit()
            logger.info("Enabled TimescaleDB extension")
            return True

        finally:
            await session.close()
            await close_db()

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
        import subprocess

        # Run alembic upgrade head with training database URL
        env = {"DATABASE_URL": database_url}
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Ran migrations successfully")
            return True
        else:
            logger.error("Migration failed", stderr=result.stderr)
            return False

    except Exception as e:
        logger.error("Failed to run migrations", error=str(e), exc_info=True)
        return False


async def sync_config() -> bool:
    """Sync training_stars.yaml configuration.

    Returns:
        True if sync succeeded
    """
    try:
        import subprocess

        result = subprocess.run(
            ["python", "-m", "scripts.sync_training_config"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Synced training configuration")
            return True
        else:
            logger.error("Config sync failed", stderr=result.stderr)
            return False

    except Exception as e:
        logger.error("Failed to sync config", error=str(e), exc_info=True)
        return False


async def main() -> None:
    """Main entry point."""
    setup_logging()
    logger.info("Starting training database setup")

    # Get training database URL
    settings = Settings()
    training_db_url = getattr(settings, "training_database_url", None)
    training_db_name = getattr(settings, "training_db", "kirby_training")

    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in .env")
        logger.info("Please add TRAINING_DATABASE_URL to your .env file")
        sys.exit(1)

    training_db_url_str = str(training_db_url)
    logger.info("Setting up training database", database=training_db_name)

    # Step 1: Create database
    logger.info("Step 1/4: Creating database...")
    if not await create_database(training_db_name, training_db_url_str):
        logger.error("Failed to create database")
        sys.exit(1)

    # Step 2: Enable TimescaleDB
    logger.info("Step 2/4: Enabling TimescaleDB...")
    if not await enable_timescaledb(training_db_url_str):
        logger.error("Failed to enable TimescaleDB")
        sys.exit(1)

    # Step 3: Run migrations
    logger.info("Step 3/4: Running migrations...")
    if not await run_migrations(training_db_url_str):
        logger.error("Failed to run migrations")
        sys.exit(1)

    # Step 4: Sync configuration
    logger.info("Step 4/4: Syncing configuration...")
    if not await sync_config():
        logger.error("Failed to sync configuration")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Training database setup complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Review config/training_stars.yaml")
    logger.info("2. Run backfill: python -m scripts.backfill_training --days=365")
    logger.info("3. Export data: python -m scripts.export_all --database=training")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## File 3: Update src/config/settings.py

Add training database URL setting to the Settings class:

```python
# Add to Settings class in src/config/settings.py

# Training Database Configuration (add after database configuration section)
training_db: str = Field(
    default="kirby_training",
    description="Training database name",
)
training_database_url: PostgresDsn | None = Field(
    default=None,
    description="Training database connection URL for ML/backtesting data",
)
training_database_pool_size: int = Field(
    default=10,
    ge=1,
    le=50,
    description="Training database connection pool size",
)
```

---

## Quick Start (Complete Setup)

### 1. Update .env file

```bash
# Add to your .env file
TRAINING_DB=kirby_training
TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:your_password_here@timescaledb:5432/kirby_training
TRAINING_DATABASE_POOL_SIZE=10
```

### 2. Run Setup Script

```bash
# One command to set up everything
docker compose exec collector python -m scripts.setup_training_db
```

This will:
- ✅ Create `kirby_training` database
- ✅ Enable TimescaleDB extension
- ✅ Run migrations (create tables)
- ✅ Sync `training_stars.yaml` configuration

### 3. Backfill Historical Data

```bash
# Backfill all training stars (365 days)
docker compose exec collector python -m scripts.backfill_training --days=365

# Or specific exchange/coin
docker compose exec collector python -m scripts.backfill_training --exchange=binance --coin=BTC --days=365
```

### 4. Verify Data

```bash
# Check how much data was collected
docker compose exec timescaledb psql -U kirby -d kirby_training -c "
SELECT
    e.name AS exchange,
    c.symbol AS coin,
    i.name AS interval,
    COUNT(*) AS candles,
    MIN(ca.time) AS oldest,
    MAX(ca.time) AS newest
FROM candles ca
JOIN starlistings s ON ca.starlisting_id = s.id
JOIN exchanges e ON s.exchange_id = e.id
JOIN coins c ON s.coin_id = c.id
JOIN intervals i ON s.interval_id = i.id
GROUP BY e.name, c.symbol, i.name
ORDER BY e.name, c.symbol, i.name;
"
```

---

## Architecture Diagram

```
Production Database (kirby)          Training Database (kirby_training)
├─ Hyperliquid real-time data        ├─ Binance historical data
├─ Real-time collectors running      ├─ One-time backfills
├─ API serves this data              ├─ Export for ML training
└─ Used for live trading             └─ Used for model development

                    ↓
            ML/Backtesting Pipeline
            ├─ Train on Binance (years of data)
            ├─ Test on Hyperliquid (validation)
            └─ Deploy to production
```

---

## Next Steps

1. ✅ Create the remaining scripts (above)
2. ✅ Update settings.py with training DB fields
3. ✅ Run setup_training_db.py
4. ✅ Backfill 1 year of Binance BTC data
5. ✅ Export data for ML training
6. ✅ Train your first model!

---

## Files Summary

| File | Status | Purpose |
|------|--------|---------|
| config/training_stars.yaml | ✅ Created | Configuration |
| docs/TRAINING_STARS.md | ✅ Created | Documentation |
| scripts/sync_training_config.py | ✅ Created | Sync config → DB |
| scripts/backfill_training.py | ⚠️ Need to create | Backfill data |
| scripts/setup_training_db.py | ⚠️ Need to create | One-command setup |
| src/config/settings.py | ⚠️ Need to update | Add training DB URL |
| .env.example | ✅ Updated | Training DB vars |

---

**Last Updated**: November 3, 2025
