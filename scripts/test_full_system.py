"""
Full system test - verify all components work.
"""
import asyncio
from decimal import Decimal

from src.db.connection import close_db, get_asyncpg_pool, get_session, init_db
from src.db.repositories import CandleRepository, StarlistingRepository

async def main():
    """Test full system functionality."""
    print("="*70)
    print("KIRBY FULL SYSTEM TEST")
    print("="*70)

    try:
        # Initialize database
        print("\n1. Initializing database connections...")
        await init_db()
        print("   [OK] AsyncPG pool created")
        print("   [OK] SQLAlchemy engine created")

        # Test asyncpg (used by collectors for bulk inserts)
        print("\n2. Testing AsyncPG connection (used by collectors)...")
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT COUNT(*) FROM starlistings")
            print(f"   [OK] Found {result} starlistings in database")

            result = await conn.fetchval("SELECT COUNT(*) FROM intervals")
            print(f"   [OK] Found {result} intervals configured")

        # Test SQLAlchemy (used by API for complex queries)
        print("\n3. Testing SQLAlchemy connection (used by API)...")
        session = await get_session()
        try:
            starlisting_repo = StarlistingRepository(session)
            starlistings = await starlisting_repo.get_active()
            print(f"   [OK] Found {len(starlistings)} active starlistings")

            for sl in starlistings[:3]:
                await session.refresh(sl, ["coin", "quote_currency", "interval", "exchange"])
                trading_pair = sl.get_trading_pair()
                print(f"      - {sl.exchange.name}/{trading_pair}/{sl.market_type.name} {sl.interval.name}")

        finally:
            await session.close()

        # Test candle operations
        print("\n4. Testing candle operations...")
        candle_repo = CandleRepository(pool)

        # Get a starlisting for testing
        session = await get_session()
        try:
            starlisting_repo = StarlistingRepository(session)
            starlistings = await starlisting_repo.get_active()
            test_starlisting = starlistings[0]

            candles = await candle_repo.get_candles(session, test_starlisting.id, limit=10)
            print(f"   [OK] Candles in database: {len(candles)}")

        finally:
            await session.close()

        print("\n" + "="*70)
        print("[SUCCESS] ALL SYSTEMS OPERATIONAL!")
        print("="*70)
        print("\nReady to start collectors and ingest real data from Hyperliquid!")
        print()

    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
