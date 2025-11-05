"""
Simple test: Backfill ONE starlisting and check num_trades.
"""
import asyncio
import sys
from scripts.backfill import BackfillService
from src.config.settings import Settings

async def main():
    print("=" * 80)
    print("SIMPLE BINANCE BACKFILL TEST")
    print("=" * 80)

    settings = Settings()
    service = BackfillService(database_url=str(settings.training_database_url))

    # Single test starlisting
    starlisting = {
        "id": 1,
        "exchange": "binance",
        "coin": "BTC",
        "quote": "USDT",
        "trading_pair": "BTC/USDT",
        "market_type": "perps",
        "interval": "1m",
    }

    print("\nBackfilling 10 minutes of BTC 1m candles...")
    print("Watch for >>> BINANCE BRANCH EXECUTING <<< in output\n")

    try:
        total = await service.backfill_starlisting(
            starlisting,
            days=0.007,  # ~10 minutes
            batch_size=20,
        )
        print(f"\n✓ Backfilled {total} candles")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()

    # Check database
    print("\nChecking database...")
    import asyncpg
    db_url = str(settings.training_database_url).replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    rows = await conn.fetch("""
        SELECT time, num_trades, volume
        FROM candles
        WHERE starlisting_id = 1
        ORDER BY time DESC
        LIMIT 5
    """)

    print("\nLast 5 candles:")
    for row in rows:
        print(f"  {row['time']}: num_trades={row['num_trades']}, volume={row['volume']}")

    has_trades = any(row['num_trades'] is not None for row in rows)

    await conn.close()

    print("\n" + "=" * 80)
    if has_trades:
        print("✅ SUCCESS: num_trades is populated!")
    else:
        print("❌ FAILURE: num_trades is NULL")
        print("\nCheck above for >>> BINANCE BRANCH EXECUTING <<< messages")
        print("If you don't see them, the Binance code path isn't running")
    print("=" * 80)

    return has_trades

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
