"""Integration tests for WebSocket API endpoints.

Note: These tests use FastAPI's WebSocket test client which simulates WebSocket
connections without requiring a running server.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.db.models import Candle


@pytest.mark.integration
class TestWebSocketEndpoint:
    """Test WebSocket API endpoint."""

    @pytest.fixture
    def sync_client(self):
        """Create a synchronous test client for WebSocket testing."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_websocket_connect(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test basic WebSocket connection."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Connection successful - websocket context manager doesn't raise
            assert websocket is not None

    @pytest.mark.asyncio
    async def test_websocket_subscribe_success(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test subscribing to valid starlistings."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Get first starlisting ID
            starlisting = seed_starlistings[0]

            # Send subscribe message
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": [starlisting.id],
                "history": 0,
            }
            websocket.send_json(subscribe_msg)

            # Receive success response
            response = websocket.receive_json()

            assert response["type"] == "success"
            assert "Subscribed" in response["message"]
            assert starlisting.id in response["starlisting_ids"]

    @pytest.mark.asyncio
    async def test_websocket_subscribe_multiple(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test subscribing to multiple starlistings."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Get multiple starlisting IDs
            starlisting_ids = [s.id for s in seed_starlistings[:3]]

            # Send subscribe message
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": starlisting_ids,
                "history": 0,
            }
            websocket.send_json(subscribe_msg)

            # Receive success response
            response = websocket.receive_json()

            assert response["type"] == "success"
            assert len(response["starlisting_ids"]) == 3
            for sid in starlisting_ids:
                assert sid in response["starlisting_ids"]

    @pytest.mark.asyncio
    async def test_websocket_subscribe_invalid_starlisting(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test subscribing to invalid starlisting ID."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send subscribe message with invalid ID
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": [99999],
                "history": 0,
            }
            websocket.send_json(subscribe_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "invalid" in response["message"].lower()
            assert response["code"] == "invalid_starlisting"

    @pytest.mark.asyncio
    async def test_websocket_subscribe_with_history(
        self, sync_client, db_session: AsyncSession, seed_base_data, seed_starlistings
    ):
        """Test subscribing with historical data request."""
        # Insert test candles
        starlisting = seed_starlistings[0]

        test_candles = [
            Candle(
                starlisting_id=starlisting.id,
                time=datetime(2024, 1, 1, 0, i, 0, tzinfo=timezone.utc),
                open=Decimal("40000.0"),
                high=Decimal("40100.0"),
                low=Decimal("39900.0"),
                close=Decimal("40050.0"),
                volume=Decimal("1234.56"),
                num_trades=42,
            )
            for i in range(10)
        ]
        db_session.add_all(test_candles)
        await db_session.commit()

        with sync_client.websocket_connect("/ws") as websocket:
            # Send subscribe message with history
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": [starlisting.id],
                "history": 5,
            }
            websocket.send_json(subscribe_msg)

            # Receive success response
            success_response = websocket.receive_json()
            assert success_response["type"] == "success"

            # Receive historical data
            historical_response = websocket.receive_json()

            assert historical_response["type"] == "historical"
            assert historical_response["starlisting_id"] == starlisting.id
            assert historical_response["count"] == 5
            assert len(historical_response["data"]) == 5

            # Verify first candle data structure
            first_candle = historical_response["data"][0]
            assert "time" in first_candle
            assert "open" in first_candle
            assert "high" in first_candle
            assert "low" in first_candle
            assert "close" in first_candle
            assert "volume" in first_candle

    @pytest.mark.asyncio
    async def test_websocket_unsubscribe(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test unsubscribing from starlistings."""
        with sync_client.websocket_connect("/ws") as websocket:
            starlisting_ids = [s.id for s in seed_starlistings[:2]]

            # Subscribe first
            subscribe_msg = {
                "action": "subscribe",
                "starlisting_ids": starlisting_ids,
                "history": 0,
            }
            websocket.send_json(subscribe_msg)
            websocket.receive_json()  # success response

            # Unsubscribe from one
            unsubscribe_msg = {
                "action": "unsubscribe",
                "starlisting_ids": [starlisting_ids[0]],
            }
            websocket.send_json(unsubscribe_msg)

            # Receive success response
            response = websocket.receive_json()

            assert response["type"] == "success"
            assert "Unsubscribed" in response["message"]
            assert starlisting_ids[0] in response["starlisting_ids"]

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test ping/pong functionality."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send ping
            ping_msg = {"action": "ping"}
            websocket.send_json(ping_msg)

            # Receive pong
            response = websocket.receive_json()

            assert response["type"] == "pong"
            assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_websocket_invalid_action(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test sending invalid action."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send invalid action
            invalid_msg = {"action": "invalid_action"}
            websocket.send_json(invalid_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "unknown action" in response["message"].lower()

    @pytest.mark.asyncio
    async def test_websocket_invalid_json(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test sending invalid JSON."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send invalid JSON
            websocket.send_text("invalid json {{{")

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "invalid json" in response["message"].lower()

    @pytest.mark.asyncio
    async def test_websocket_validation_error(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test validation error (missing required fields)."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send subscribe message without starlisting_ids
            invalid_msg = {"action": "subscribe"}
            websocket.send_json(invalid_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "validation" in response["message"].lower()

    @pytest.mark.asyncio
    async def test_websocket_subscribe_empty_list(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test subscribing with empty starlisting_ids list."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send subscribe message with empty list
            invalid_msg = {"action": "subscribe", "starlisting_ids": [], "history": 0}
            websocket.send_json(invalid_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_websocket_subscribe_too_many_ids(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test subscribing with too many starlisting_ids."""
        with sync_client.websocket_connect("/ws") as websocket:
            # Send subscribe message with > 100 IDs
            invalid_msg = {
                "action": "subscribe",
                "starlisting_ids": list(range(1, 102)),
                "history": 0,
            }
            websocket.send_json(invalid_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_websocket_history_too_large(
        self, sync_client, seed_base_data, seed_starlistings
    ):
        """Test requesting too much history."""
        with sync_client.websocket_connect("/ws") as websocket:
            starlisting = seed_starlistings[0]

            # Send subscribe message with history > 1000
            invalid_msg = {
                "action": "subscribe",
                "starlisting_ids": [starlisting.id],
                "history": 1001,
            }
            websocket.send_json(invalid_msg)

            # Receive error response
            response = websocket.receive_json()

            assert response["type"] == "error"
