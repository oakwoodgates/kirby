"""
Simple test to collect real data from Hyperliquid for 30 seconds.
"""
import asyncio
import signal

from src.collectors.main import CollectorManager
from src.db.connection import close_db, init_db
from src.utils.logging import setup_logging


async def main():
    """Run collector for a short test period."""
    print("="*70)
    print("KIRBY - HYPERLIQUID REAL DATA COLLECTION TEST")
    print("="*70)
    print()

    # Set up logging
    setup_logging()

    try:
        # Initialize database
        print("1. Initializing database...")
        await init_db()
        print("   [OK] Database initialized\n")

        # Create collector manager and register Hyperliquid collector
        print("2. Setting up Hyperliquid collector...")
        manager = CollectorManager()

        from src.collectors.hyperliquid import HyperliquidCollector
        hyperliquid = HyperliquidCollector()
        manager.register_collector(hyperliquid)
        print("   [OK] Collector registered\n")

        # Initialize collectors (loads starlistings)
        print("3. Initializing collector...")
        await hyperliquid.initialize()
        print(f"   [OK] Loaded {len(hyperliquid.starlistings)} starlistings\n")

        # Start collectors (non-blocking)
        print("4. Starting collector...")
        await manager.start_all()
        print("   [OK] Collector started\n")

        print("5. Collecting real-time data for 30 seconds...")
        print("   (Watch for incoming candle data...)\n")

        # Run for 30 seconds
        await asyncio.sleep(30)

        print("\n6. Stopping collector...")
        await manager.stop_all()
        print("   [OK] Collector stopped\n")

        # Check what we collected
        from src.db.connection import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        if pool:
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM candles")
                print(f"7. Data collected: {count} candles in database")

                if count > 0:
                    # Show sample
                    sample = await conn.fetch("""
                        SELECT c.time, co.symbol AS coin, qc.symbol AS quote,
                               mt.name AS market_type, i.name AS interval,
                               c.open, c.high, c.low, c.close, c.volume
                        FROM candles c
                        JOIN starlistings s ON c.starlisting_id = s.id
                        JOIN coins co ON s.coin_id = co.id
                        JOIN quote_currencies qc ON s.quote_currency_id = qc.id
                        JOIN market_types mt ON s.market_type_id = mt.id
                        JOIN intervals i ON s.interval_id = i.id
                        ORDER BY c.time DESC
                        LIMIT 5
                    """)

                    print("\n   Sample candles:")
                    for row in sample:
                        pair = f"{row['coin']}/{row['quote']}"
                        print(f"      {row['time']} | {pair} {row['market_type']} {row['interval']} | "
                              f"O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']}")

        print("\n" + "="*70)
        print("[SUCCESS] Real data collection test completed!")
        print("="*70)
        print()

    except KeyboardInterrupt:
        print("\n\nStopping...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
