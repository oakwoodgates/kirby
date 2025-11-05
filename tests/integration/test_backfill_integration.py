"""
Integration test for Binance num_trades backfill.
Tests the full flow from BackfillService to database.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from scripts.backfill import BackfillService
from src.config.settings import Settings
from src.utils.logging import setup_logging

# Setup logging
setup_logging("development")

async def test_binance_backfill():
    """Test Binance backfill with num_trades."""
    print("=" * 80)
    print("Integration Test: Binance Backfill with num_trades")
    print("=" * 80)

    # Get training database URL
    settings = Settings()
    training_db_url = str(settings.training_database_url)
    print(f"\n1. Training DB URL: {training_db_url}")

    # Create backfill service
    print("\n2. Creating BackfillService...")
    service = BackfillService(database_url=training_db_url)

    # Create a test starlisting for Binance BTC/USDT perps 1m
    test_starlisting = {
        "id": 1,
        "exchange": "binance",
        "coin": "BTC",
        "quote": "USDT",
        "trading_pair": "BTC/USDT",
        "market_type": "perps",
        "interval": "1m",
    }

    print(f"\n3. Test starlisting:")
    for key, value in test_starlisting.items():
        print(f"   {key}: {value}")

    print(f"\n4. Starting backfill (1 hour of data)...")
    print(f"   This will show if Binance raw API path is executed...")

    try:
        # Backfill just 1 hour to be fast
        total_candles = await service.backfill_starlisting(
            test_starlisting,
            days=0.042,  # ~1 hour (1/24 of a day)
            batch_size=100,
        )
        print(f"\n5. Backfill complete!")
        print(f"   Total candles stored: {total_candles}")

    except Exception as e:
        print(f"\n5. Backfill FAILED:")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await service.close()

    print("\n6. Checking database for num_trades...")

    # Check database using asyncpg directly
    import asyncpg
    db_url_asyncpg = training_db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(db_url_asyncpg)

        # Query for num_trades
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(num_trades) as with_trades,
                MIN(num_trades) as min_trades,
                MAX(num_trades) as max_trades,
                ROUND(AVG(num_trades), 0) as avg_trades
            FROM candles c
            JOIN starlistings s ON c.starlisting_id = s.id
            JOIN exchanges e ON s.exchange_id = e.id
            WHERE e.name = 'binance'
              AND s.id = 1
              AND c.time > NOW() - INTERVAL '2 hours'
        """)

        print(f"   Total candles: {row['total']}")
        print(f"   With num_trades: {row['with_trades']}")
        print(f"   Min trades: {row['min_trades']}")
        print(f"   Max trades: {row['max_trades']}")
        print(f"   Avg trades: {row['avg_trades']}")

        # Get sample candles
        print(f"\n7. Sample candles:")
        rows = await conn.fetch("""
            SELECT time, open, close, volume, num_trades
            FROM candles c
            JOIN starlistings s ON c.starlisting_id = s.id
            JOIN exchanges e ON s.exchange_id = e.id
            WHERE e.name = 'binance'
              AND s.id = 1
              AND c.time > NOW() - INTERVAL '2 hours'
            ORDER BY time DESC
            LIMIT 5
        """)

        for row in rows:
            print(f"   {row['time']}: num_trades = {row['num_trades']}")

        await conn.close()

        # Check if successful
        success = row['with_trades'] > 0

        print("\n" + "=" * 80)
        if success:
            print("✅ SUCCESS: num_trades field is populated!")
        else:
            print("❌ FAILURE: num_trades field is still NULL")
            print("\nDEBUG INFO:")
            print("- Check logs above for 'Using Binance raw API' message")
            print("- Check for 'Binance raw candle sample' log message")
            print("- If these don't appear, the Binance path is not being executed")
        print("=" * 80)

        return success

    except Exception as e:
        print(f"   Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_binance_backfill())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
