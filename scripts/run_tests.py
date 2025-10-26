#!/usr/bin/env python3
"""
Script to run tests with proper database setup.
"""
import asyncio
import subprocess
import sys

from sqlalchemy import create_engine, text

from src.config.settings import settings


async def setup_test_database():
    """Create test database if it doesn't exist."""
    # Connect to postgres database to create test database
    base_url = settings.database_url.rsplit("/", 1)[0]
    engine = create_engine(f"{base_url}/postgres")

    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")

        # Drop and recreate test database
        try:
            conn.execute(text("DROP DATABASE IF EXISTS kirby_test"))
            print("Dropped existing test database")
        except Exception as e:
            print(f"Could not drop test database: {e}")

        try:
            conn.execute(text("CREATE DATABASE kirby_test"))
            print("Created test database")
        except Exception as e:
            print(f"Could not create test database: {e}")

    engine.dispose()


def run_tests(test_args: list[str] | None = None):
    """Run pytest with optional arguments."""
    cmd = ["pytest"]

    if test_args:
        cmd.extend(test_args)
    else:
        # Default: run all tests with coverage
        cmd.extend([
            "-v",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html",
        ])

    result = subprocess.run(cmd)
    return result.returncode


def main():
    """Main entry point."""
    print("Setting up test database...")
    asyncio.run(setup_test_database())

    print("\nRunning tests...")
    # Pass through any command line arguments to pytest
    exit_code = run_tests(sys.argv[1:] if len(sys.argv) > 1 else None)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
