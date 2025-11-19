"""WebSocket test client for Kirby API.

This script demonstrates how to connect to the Kirby WebSocket API and subscribe
to real-time candle updates.

Usage:
    python scripts/test_websocket_client.py

Environment Variables:
    API_KEY: API key for authentication (required)
    WEBSOCKET_URL: WebSocket URL (default: ws://localhost:8000/ws)
    STARLISTING_IDS: Comma-separated starlisting IDs to subscribe to (default: 1,2)
    HISTORY: Number of historical candles to request (default: 10)
"""

import asyncio
import json
import os
import sys
from datetime import datetime

import websockets
from structlog import get_logger

logger = get_logger(__name__)


class KirbyWebSocketClient:
    """WebSocket client for Kirby API."""

    def __init__(
        self,
        api_key: str,
        url: str = "ws://localhost:8000/ws",
        starlisting_ids: list[int] = None,
        history: int = 10,
    ):
        """Initialize the WebSocket client.

        Args:
            api_key: API key for authentication
            url: WebSocket URL (base URL without query params)
            starlisting_ids: List of starlisting IDs to subscribe to
            history: Number of historical candles to request
        """
        # Add API key as query parameter
        separator = "&" if "?" in url else "?"
        self.url = f"{url}{separator}api_key={api_key}"
        self.starlisting_ids = starlisting_ids or [1, 2]
        self.history = history
        self.websocket = None
        self.running = False

    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            # Hide API key in logs
            display_url = self.url.split("api_key=")[0] + "api_key=***"
            print(f"[{datetime.now()}] Connecting to {display_url}")
            self.websocket = await websockets.connect(self.url)
            self.running = True
            print(f"[{datetime.now()}] Connected successfully!")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Connection failed: {e}")
            return False

    async def subscribe(self):
        """Subscribe to starlistings."""
        if not self.websocket:
            print("Not connected!")
            return False

        try:
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": self.starlisting_ids,
                "history": self.history,
            }

            print(
                f"\n[{datetime.now()}] Subscribing to starlistings: {self.starlisting_ids}"
            )
            print(f"  Requesting {self.history} historical candles...")

            await self.websocket.send(json.dumps(subscribe_msg))
            return True

        except Exception as e:
            print(f"[{datetime.now()}] Subscribe failed: {e}")
            return False

    async def unsubscribe(self, starlisting_ids: list[int]):
        """Unsubscribe from starlistings.

        Args:
            starlisting_ids: List of starlisting IDs to unsubscribe from
        """
        if not self.websocket:
            print("Not connected!")
            return False

        try:
            unsubscribe_msg = {
                "action": "unsubscribe",
                "starlisting_ids": starlisting_ids,
            }

            print(
                f"\n[{datetime.now()}] Unsubscribing from starlistings: {starlisting_ids}"
            )
            await self.websocket.send(json.dumps(unsubscribe_msg))
            return True

        except Exception as e:
            print(f"[{datetime.now()}] Unsubscribe failed: {e}")
            return False

    async def ping(self):
        """Send a ping message."""
        if not self.websocket:
            print("Not connected!")
            return False

        try:
            ping_msg = {"action": "ping"}
            await self.websocket.send(json.dumps(ping_msg))
            return True

        except Exception as e:
            print(f"[{datetime.now()}] Ping failed: {e}")
            return False

    async def receive_messages(self):
        """Receive and print messages from the server."""
        if not self.websocket:
            print("Not connected!")
            return

        print(f"\n[{datetime.now()}] Listening for messages...\n")
        print("=" * 80)

        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "success":
                    print(f"\n✅ SUCCESS: {data.get('message')}")
                    if data.get("starlisting_ids"):
                        print(f"   Starlisting IDs: {data.get('starlisting_ids')}")

                elif msg_type == "error":
                    print(f"\n❌ ERROR: {data.get('message')}")
                    if data.get("code"):
                        print(f"   Error code: {data.get('code')}")

                elif msg_type == "pong":
                    print(f"\n🏓 PONG: {data.get('timestamp')}")

                elif msg_type == "ping":
                    print(f"\n🏓 PING: {data.get('timestamp')}")

                elif msg_type == "historical":
                    print(f"\n📊 HISTORICAL CANDLE DATA:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(
                        f"   Market Type: {data.get('market_type')} | Interval: {data.get('interval')}"
                    )
                    print(f"   Candles: {data.get('count')}")

                    # Print first and last candle
                    candles = data.get("data", [])
                    if candles:
                        first = candles[0]
                        last = candles[-1]
                        print(
                            f"   First candle: {first.get('time')} | Close: {first.get('close')}"
                        )
                        print(
                            f"   Last candle:  {last.get('time')} | Close: {last.get('close')}"
                        )

                elif msg_type == "historical_funding":
                    print(f"\n💰 HISTORICAL FUNDING RATE DATA:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(f"   Market Type: {data.get('market_type')}")
                    print(f"   Snapshots: {data.get('count')}")

                    # Print first and last snapshot
                    snapshots = data.get("data", [])
                    if snapshots:
                        first = snapshots[0]
                        last = snapshots[-1]
                        print(
                            f"   First snapshot: {first.get('time')} | Rate: {first.get('funding_rate')}"
                        )
                        print(
                            f"   Last snapshot:  {last.get('time')} | Rate: {last.get('funding_rate')}"
                        )

                elif msg_type == "historical_oi":
                    print(f"\n📈 HISTORICAL OPEN INTEREST DATA:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(f"   Market Type: {data.get('market_type')}")
                    print(f"   Snapshots: {data.get('count')}")

                    # Print first and last snapshot
                    snapshots = data.get("data", [])
                    if snapshots:
                        first = snapshots[0]
                        last = snapshots[-1]
                        print(
                            f"   First snapshot: {first.get('time')} | OI: {first.get('open_interest')}"
                        )
                        print(
                            f"   Last snapshot:  {last.get('time')} | OI: {last.get('open_interest')}"
                        )

                elif msg_type == "candle":
                    candle_data = data.get("data", {})
                    print(f"\n🕯️  NEW CANDLE UPDATE:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(
                        f"   Market Type: {data.get('market_type')} | Interval: {data.get('interval')}"
                    )
                    print(f"   Time: {candle_data.get('time')}")
                    print(
                        f"   OHLC: {candle_data.get('open')} / {candle_data.get('high')} / "
                        f"{candle_data.get('low')} / {candle_data.get('close')}"
                    )
                    print(f"   Volume: {candle_data.get('volume')}")
                    if candle_data.get("num_trades"):
                        print(f"   Trades: {candle_data.get('num_trades')}")

                elif msg_type == "funding":
                    funding_data = data.get("data", {})
                    print(f"\n💰 NEW FUNDING RATE UPDATE:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(f"   Market Type: {data.get('market_type')}")
                    print(f"   Time: {funding_data.get('time')}")
                    print(f"   Funding Rate: {funding_data.get('funding_rate')}")
                    print(f"   Premium: {funding_data.get('premium')}")
                    if funding_data.get("mark_price"):
                        print(f"   Mark Price: {funding_data.get('mark_price')}")
                    if funding_data.get("index_price"):
                        print(f"   Index Price: {funding_data.get('index_price')}")
                    if funding_data.get("next_funding_time"):
                        print(f"   Next Funding: {funding_data.get('next_funding_time')}")

                elif msg_type == "open_interest":
                    oi_data = data.get("data", {})
                    print(f"\n📈 NEW OPEN INTEREST UPDATE:")
                    print(f"   Starlisting ID: {data.get('starlisting_id')}")
                    print(
                        f"   Trading Pair: {data.get('trading_pair')} ({data.get('exchange')})"
                    )
                    print(f"   Market Type: {data.get('market_type')}")
                    print(f"   Time: {oi_data.get('time')}")
                    print(f"   Open Interest: {oi_data.get('open_interest')}")
                    if oi_data.get("notional_value"):
                        print(f"   Notional Value: {oi_data.get('notional_value')}")
                    if oi_data.get("day_base_volume"):
                        print(f"   Day Volume: {oi_data.get('day_base_volume')}")

                else:
                    print(f"\n📨 Unknown message type: {msg_type}")
                    print(f"   Data: {json.dumps(data, indent=2)}")

                print("-" * 80)

        except websockets.exceptions.ConnectionClosed:
            print(f"\n[{datetime.now()}] Connection closed by server")
            self.running = False
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] Interrupted by user")
            self.running = False
        except Exception as e:
            print(f"\n[{datetime.now()}] Error receiving messages: {e}")
            self.running = False

    async def run(self):
        """Run the WebSocket client."""
        # Connect
        if not await self.connect():
            return

        # Subscribe
        if not await self.subscribe():
            await self.close()
            return

        # Start receiving messages
        try:
            await self.receive_messages()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] Shutting down...")
        finally:
            await self.close()

    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            print(f"\n[{datetime.now()}] Closing connection...")
            await self.websocket.close()
            self.websocket = None
            self.running = False
            print(f"[{datetime.now()}] Connection closed")


async def main():
    """Main function."""
    # Get configuration from environment variables
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("ERROR: API_KEY environment variable is required")
        print("\nUsage:")
        print('  export API_KEY="kb_your_api_key_here"')
        print("  python scripts/test_websocket_client.py")
        sys.exit(1)

    url = os.getenv("WEBSOCKET_URL", "ws://localhost:8000/ws")
    starlisting_ids_str = os.getenv("STARLISTING_IDS", "1,2")
    history = int(os.getenv("HISTORY", "10"))

    # Parse starlisting IDs
    starlisting_ids = [int(sid.strip()) for sid in starlisting_ids_str.split(",")]

    print("=" * 80)
    print("Kirby WebSocket Test Client")
    print("=" * 80)
    print(f"WebSocket URL: {url}")
    print(f"API Key: {api_key[:10]}... (hidden)")
    print(f"Starlisting IDs: {starlisting_ids}")
    print(f"Historical candles: {history}")
    print("=" * 80)
    print("\nPress Ctrl+C to exit\n")

    # Create and run client
    client = KirbyWebSocketClient(
        api_key=api_key,
        url=url,
        starlisting_ids=starlisting_ids,
        history=history,
    )

    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
