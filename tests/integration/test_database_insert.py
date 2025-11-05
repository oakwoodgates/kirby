"""
Test database insert with num_trades to verify the full data flow.
This simulates what happens after Binance API returns data.
"""
import asyncio
import sys
from datetime import datetime, timezone
from scripts.backfill import BackfillService
from src.config.settings import Settings
from src.utils.helpers import normalize_candle_data
from src.db.repositories import CandleRepository


async def test_database_insert():
    """Test that num_trades makes it through to the database."""
    print("=" * 80)
    print("Testing Full Data Flow: Normalization → Database Insert")
    print("=" * 80)

    # Mock Binance raw API response (12-field format)
    mock_binance_klines = [
        [
            1730752800000,      # Open time
            "68500.50",         # Open
            "68750.00",         # High
            "68400.25",         # Low
            "68650.75",         # Close
            "1234.56789",       # Volume
            1730752859999,      # Close time
            "84567890.12",      # Quote volume
            5432,               # num_trades ← THIS IS WHAT WE WANT
            "617.28394",        # Taker buy base
            "42345678.90",      # Taker buy quote
            "0"                 # Ignore
        ],
        [
            1730752860000,
            "68650.75",
            "68700.00",
            "68600.00",
            "68680.00",
            "987.65432",
            1730752919999,
            "67890123.45",
            3210,               # num_trades
            "500.12345",
            "34567890.12",
            "0"
        ],
    ]

    print("\n1. Mock Binance klines:")
    print(f"   Number of klines: {len(mock_binance_klines)}")
    print(f"   First kline num_trades: {mock_binance_klines[0][8]}")
    print(f"   Second kline num_trades: {mock_binance_klines[1][8]}")

    # Normalize using binance_raw source
    print("\n2. Normalizing klines with 'binance_raw' source...")
    normalized_candles = []
    for i, kline in enumerate(mock_binance_klines):
        normalized = normalize_candle_data(kline, source="binance_raw")
        normalized_candles.append(normalized)
        print(f"   Kline {i+1}: time={normalized['time']}, num_trades={normalized['num_trades']}")

    # Prepare for database insert (same as backfill.py does)
    print("\n3. Preparing candles for database insert...")
    settings = Settings()
    service = BackfillService(database_url=str(settings.training_database_url))

    # Use starlisting_id=1 (binance/BTC/USDT/perps/1m from training config)
    starlisting_id = 1

    candles_batch = []
    for normalized in normalized_candles:
        candle_dict = {
            "time": normalized["time"],
            "starlisting_id": starlisting_id,
            **normalized,  # Spreads all fields including num_trades
        }
        candles_batch.append(candle_dict)
        print(f"   Candle dict keys: {list(candle_dict.keys())}")
        print(f"   Candle dict num_trades: {candle_dict.get('num_trades')}")

    # Insert into database (same way backfill.py does it)
    print("\n4. Inserting into database...")
    try:
        pool = await service.get_db_pool()
        candle_repo = CandleRepository(pool)
        stored = await candle_repo.upsert_candles(candles_batch)
        print(f"   ✓ Inserted {stored} candles")
    except Exception as e:
        print(f"   ✗ Error inserting: {e}")
        import traceback
        traceback.print_exc()
        await service.close()
        return False

    # Verify in database
    print("\n5. Verifying in database...")
    import asyncpg
    db_url = str(settings.training_database_url).replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(db_url)

        # Query for the candles we just inserted
        rows = await conn.fetch("""
            SELECT time, open, close, volume, num_trades
            FROM candles
            WHERE starlisting_id = $1
              AND time >= $2
            ORDER BY time
        """, starlisting_id, normalized_candles[0]["time"])

        print(f"   Found {len(rows)} candles in database:")
        all_have_trades = True
        for row in rows:
            has_trades = row['num_trades'] is not None
            status = "✓" if has_trades else "✗"
            print(f"   {status} time={row['time']}, num_trades={row['num_trades']}")
            if not has_trades:
                all_have_trades = False

        await conn.close()

        # Final verdict
        print("\n" + "=" * 80)
        if all_have_trades and len(rows) == len(candles_batch):
            print("✅ SUCCESS: All candles have num_trades in database!")
            print(f"✅ Expected: {len(candles_batch)} candles with num_trades")
            print(f"✅ Got: {len(rows)} candles, all with num_trades")
        else:
            print("❌ FAILURE: num_trades not properly saved to database")
            print(f"   Expected: {len(candles_batch)} candles")
            print(f"   Found: {len(rows)} candles")
            print(f"   With num_trades: {sum(1 for r in rows if r['num_trades'] is not None)}")
        print("=" * 80)

        await service.close()
        return all_have_trades

    except Exception as e:
        print(f"   ✗ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        await service.close()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_database_insert())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
