"""
Comprehensive API endpoint testing script.
"""

import requests
import json
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, url, expected_status=200):
    """Test a single endpoint and print results."""
    try:
        response = requests.get(url, timeout=10)
        status = "[OK]" if response.status_code == expected_status else "[FAIL]"
        print(f"{status} {name}: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"  > Returned {len(data)} items")
            elif isinstance(data, dict) and 'status' in data:
                print(f"  > Status: {data.get('status')}")
            return True
        else:
            print(f"  > Error: {response.text[:100]}")
            return False

    except Exception as e:
        print(f"[FAIL] {name}: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("API Endpoint Testing")
    print("=" * 60)

    # Wait for server to start
    print("\nWaiting for server to start...")
    time.sleep(3)

    results = {}

    # Test Health Endpoints
    print("\n--- Health Endpoints ---")
    results['health'] = test_endpoint(
        "Health Check",
        f"{BASE_URL}/api/v1/health"
    )
    results['health_db'] = test_endpoint(
        "Database Health",
        f"{BASE_URL}/api/v1/health/database"
    )
    results['health_detailed'] = test_endpoint(
        "Detailed Health",
        f"{BASE_URL}/api/v1/health/detailed"
    )

    # Test Listings Endpoints
    print("\n--- Listings Endpoints ---")
    results['listings'] = test_endpoint(
        "Get All Listings",
        f"{BASE_URL}/api/v1/listings"
    )
    results['listing_1'] = test_endpoint(
        "Get Listing 1",
        f"{BASE_URL}/api/v1/listings/1"
    )

    # Test Candles Endpoints
    print("\n--- Candles Endpoints ---")
    results['candles'] = test_endpoint(
        "Query Candles (listing_id=1)",
        f"{BASE_URL}/api/v1/candles?listing_id=1&interval=1m&limit=10"
    )
    results['candles_latest_all'] = test_endpoint(
        "Latest Candles (all listings)",
        f"{BASE_URL}/api/v1/candles/latest?interval=1m"
    )
    results['candles_latest_1'] = test_endpoint(
        "Latest Candle (listing_id=1)",
        f"{BASE_URL}/api/v1/candles/1/latest?interval=1m"
    )

    # Test Funding Rates Endpoints
    print("\n--- Funding Rates Endpoints ---")
    results['funding'] = test_endpoint(
        "Query Funding Rates (listing_id=1)",
        f"{BASE_URL}/api/v1/funding-rates?listing_id=1&limit=10"
    )
    results['funding_latest_all'] = test_endpoint(
        "Latest Funding Rates (all listings)",
        f"{BASE_URL}/api/v1/funding-rates/latest"
    )
    results['funding_latest_1'] = test_endpoint(
        "Latest Funding Rate (listing_id=1)",
        f"{BASE_URL}/api/v1/funding-rates/1/latest"
    )

    # Test Open Interest Endpoints
    print("\n--- Open Interest Endpoints ---")
    results['oi'] = test_endpoint(
        "Query Open Interest (listing_id=1)",
        f"{BASE_URL}/api/v1/open-interest?listing_id=1&limit=10"
    )
    results['oi_latest_all'] = test_endpoint(
        "Latest Open Interest (all listings)",
        f"{BASE_URL}/api/v1/open-interest/latest"
    )
    results['oi_latest_1'] = test_endpoint(
        "Latest Open Interest (listing_id=1)",
        f"{BASE_URL}/api/v1/open-interest/1/latest"
    )

    # Test Market Snapshot Endpoints
    print("\n--- Market Snapshot Endpoints ---")
    results['snapshot_all'] = test_endpoint(
        "Market Snapshot (all listings)",
        f"{BASE_URL}/api/v1/market/snapshot"
    )
    results['snapshot_1'] = test_endpoint(
        "Market Snapshot (listing_id=1)",
        f"{BASE_URL}/api/v1/market/1/snapshot"
    )

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Passed: {passed}/{total} ({100*passed//total}%)")

    if passed == total:
        print("\n[OK] All tests passed!")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
