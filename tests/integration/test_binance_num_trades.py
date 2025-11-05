"""
Test script to verify Binance raw API num_trades capture.
"""
import asyncio
from binance.client import Client
from src.utils.helpers import normalize_candle_data


async def test_binance_raw_api():
    """Test fetching and normalizing Binance data with num_trades."""
    print("=" * 80)
    print("Testing Binance Raw API for num_trades Field")
    print("=" * 80)

    # Create Binance client (no API key needed for public data)
    print("\n1. Creating Binance client...")
    try:
        client = Client()
        print("   ✓ Binance client created")
    except Exception as e:
        print(f"   ✗ Error creating client: {e}")
        print("   Note: VPN required if geo-blocked")
        return

    # Fetch klines for BTC/USDT
    print("\n2. Fetching BTC/USDT klines (1m interval, limit 5)...")
    try:
        klines = client.get_klines(
            symbol='BTCUSDT',
            interval='1m',
            limit=5
        )
        print(f"   ✓ Fetched {len(klines)} klines")
    except Exception as e:
        print(f"   ✗ Error fetching klines: {e}")
        return

    # Show first raw kline
    print("\n3. First raw kline (12-field array):")
    if klines:
        first_kline = klines[0]
        print(f"   Number of fields: {len(first_kline)}")
        print(f"   [0] Open time:     {first_kline[0]}")
        print(f"   [1] Open:          {first_kline[1]}")
        print(f"   [2] High:          {first_kline[2]}")
        print(f"   [3] Low:           {first_kline[3]}")
        print(f"   [4] Close:         {first_kline[4]}")
        print(f"   [5] Volume:        {first_kline[5]}")
        print(f"   [6] Close time:    {first_kline[6]}")
        print(f"   [7] Quote volume:  {first_kline[7]}")
        print(f"   [8] NUM_TRADES:    {first_kline[8]} ← THIS IS WHAT WE WANT!")
        print(f"   [9] Taker buy base: {first_kline[9]}")
        print(f"   [10] Taker buy quote: {first_kline[10]}")
        print(f"   [11] Ignore:       {first_kline[11]}")

    # Normalize using binance_raw source
    print("\n4. Normalizing with 'binance_raw' source...")
    try:
        normalized = normalize_candle_data(first_kline, source="binance_raw")
        print("   ✓ Normalization successful")
        print(f"   Normalized candle:")
        print(f"     time:       {normalized['time']}")
        print(f"     open:       {normalized['open']}")
        print(f"     high:       {normalized['high']}")
        print(f"     low:        {normalized['low']}")
        print(f"     close:      {normalized['close']}")
        print(f"     volume:     {normalized['volume']}")
        print(f"     num_trades: {normalized['num_trades']} ← CAPTURED!")
    except Exception as e:
        print(f"   ✗ Error normalizing: {e}")
        return

    # Test all klines
    print("\n5. Testing all 5 klines:")
    all_have_trades = True
    for i, kline in enumerate(klines):
        normalized = normalize_candle_data(kline, source="binance_raw")
        num_trades = normalized['num_trades']
        print(f"   Kline {i+1}: num_trades = {num_trades}")
        if num_trades is None:
            all_have_trades = False

    print("\n" + "=" * 80)
    if all_have_trades:
        print("✅ SUCCESS: All klines have num_trades field populated!")
    else:
        print("❌ FAILURE: Some klines missing num_trades")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_binance_raw_api())
