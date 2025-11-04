#!/usr/bin/env python3
"""
Run Alembic migrations on the training database.

This script explicitly targets the training database (kirby_training)
instead of the production database (kirby).
"""

import logging
import os
import subprocess
import sys

import structlog

from src.config.settings import Settings


def setup_logging() -> None:
    """Setup logging configuration."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def main() -> None:
    """Run Alembic migrations on training database."""
    setup_logging()
    logger = structlog.get_logger("kirby.scripts.migrate_training_db")

    logger.info("Starting training database migration")

    # Get settings
    settings = Settings()
    training_db_url = getattr(settings, "training_database_url", None)

    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in environment")
        sys.exit(1)

    # Convert asyncpg URL to psycopg2 format for Alembic
    training_url_psycopg2 = str(training_db_url).replace(
        "postgresql+asyncpg://", "postgresql://"
    )

    logger.info("Training database URL configured", url=training_url_psycopg2.split('@')[1] if '@' in training_url_psycopg2 else "")

    try:
        # Run Alembic upgrade via subprocess with DATABASE_URL override
        logger.info("Running Alembic upgrade head on training database")
        env = os.environ.copy()
        env["DATABASE_URL"] = training_url_psycopg2

        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        # Log output
        if result.stdout:
            logger.info("Alembic output", output=result.stdout.strip())

        logger.info("Training database migrations completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error("Training database migration failed",
                    error=str(e),
                    stdout=e.stdout if e.stdout else "",
                    stderr=e.stderr if e.stderr else "")
        sys.exit(1)
    except Exception as e:
        logger.error("Training database migration failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
