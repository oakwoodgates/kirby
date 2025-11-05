"""
Test normalization of Binance raw API format (no API calls required).
"""
from src.utils.helpers import normalize_candle_data

# Mock Binance raw API response (12-field format)
# This is what Binance actually returns
mock_binance_kline = [
    1730752800000,      # [0] Open time (timestamp in ms)
    "68500.50",         # [1] Open price
    "68750.00",         # [2] High price
    "68400.25",         # [3] Low price
    "68650.75",         # [4] Close price
    "1234.56789",       # [5] Volume
    1730752859999,      # [6] Close time
    "84567890.12",      # [7] Quote asset volume
    5432,               # [8] Number of trades ← THIS IS WHAT WE WANT
    "617.28394",        # [9] Taker buy base asset volume
    "42345678.90",      # [10] Taker buy quote asset volume
    "0"                 # [11] Ignore
]

print("=" * 80)
print("Testing Binance Raw API Normalization (No API Calls)")
print("=" * 80)

print("\n1. Mock Binance kline (12-field array):")
print(f"   Number of fields: {len(mock_binance_kline)}")
print(f"   [8] num_trades: {mock_binance_kline[8]}")

print("\n2. Normalizing with source='binance_raw'...")
try:
    normalized = normalize_candle_data(mock_binance_kline, source="binance_raw")
    print("   ✓ Normalization successful!")

    print("\n3. Normalized candle:")
    for key, value in normalized.items():
        print(f"   {key:12} = {value}")

    print("\n4. Verification:")
    if normalized.get('num_trades') == 5432:
        print("   ✅ SUCCESS: num_trades correctly extracted from index 8!")
        print(f"   ✅ Value: {normalized['num_trades']} (expected: 5432)")
    else:
        print(f"   ❌ FAILURE: num_trades = {normalized.get('num_trades')} (expected: 5432)")

except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
