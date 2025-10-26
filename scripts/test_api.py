"""
Quick test of API endpoints.
"""
import asyncio
import sys

import httpx
from src.api.main import app

async def test_api():
    """Test all API endpoints."""
    print("Testing API endpoints...")
    print("="*60)

    # Create test client
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Test root
        print("\n1. Testing root endpoint (/)...")
        response = await client.get("/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test health
        print("\n2. Testing health endpoint (/health)...")
        response = await client.get("/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test starlistings
        print("\n3. Testing starlistings endpoint (/starlistings)...")
        response = await client.get("/starlistings")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total: {data['total_count']} starlistings")
        if data['starlistings']:
            print(f"First starlisting: {data['starlistings'][0]['trading_pair']} - {data['starlistings'][0]['interval']}")

        # Test candles (should be empty)
        print("\n4. Testing candles endpoint (/candles/hyperliquid/BTC/USD/perps/1m)...")
        response = await client.get("/candles/hyperliquid/BTC/USD/perps/1m?limit=10")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Metadata: {data['metadata']}")
        print(f"Candles count: {len(data['data'])}")

    print("\n" + "="*60)
    print("All API tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_api())
