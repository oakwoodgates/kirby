"""Unit tests for WebSocket connection manager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.websocket_manager import ConnectionManager


class TestConnectionManager:
    """Test ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager(max_connections=10, heartbeat_interval=30)

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket connection."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    def test_initialization(self, manager):
        """Test ConnectionManager initialization."""
        assert manager.max_connections == 10
        assert manager.heartbeat_interval == 30
        assert manager.connection_count == 0
        assert not manager.is_at_capacity

    def test_connection_count(self, manager, mock_websocket):
        """Test connection count property."""
        assert manager.connection_count == 0

        # Manually add connection to bypass accept()
        manager.connections[mock_websocket] = set()

        assert manager.connection_count == 1

    def test_is_at_capacity(self, manager, mock_websocket):
        """Test capacity check."""
        # Add connections up to limit
        for i in range(10):
            ws = MagicMock()
            manager.connections[ws] = set()

        assert manager.is_at_capacity

    @pytest.mark.asyncio
    async def test_connect_success(self, manager, mock_websocket):
        """Test successful connection."""
        result = await manager.connect(mock_websocket)

        assert result is True
        assert mock_websocket in manager.connections
        assert manager.connections[mock_websocket] == set()
        assert manager.connection_count == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_at_capacity(self, manager, mock_websocket):
        """Test connection rejection when at capacity."""
        # Fill up to capacity
        for i in range(10):
            ws = MagicMock()
            manager.connections[ws] = set()

        # Try to connect when at capacity
        new_ws = MagicMock()
        new_ws.accept = AsyncMock()

        result = await manager.connect(new_ws)

        assert result is False
        assert new_ws not in manager.connections
        new_ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """Test disconnection cleanup."""
        # Setup: connect and subscribe
        manager.connections[mock_websocket] = {1, 2, 3}
        manager.subscribers[1] = {mock_websocket}
        manager.subscribers[2] = {mock_websocket}
        manager.subscribers[3] = {mock_websocket}

        # Mock heartbeat task
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        manager._heartbeat_tasks[mock_websocket] = mock_task

        # Disconnect
        await manager.disconnect(mock_websocket)

        # Verify cleanup
        assert mock_websocket not in manager.connections
        assert 1 not in manager.subscribers
        assert 2 not in manager.subscribers
        assert 3 not in manager.subscribers
        assert mock_websocket not in manager._heartbeat_tasks
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe(self, manager, mock_websocket):
        """Test subscribing to starlistings."""
        manager.connections[mock_websocket] = set()

        await manager.subscribe(mock_websocket, [1, 2, 3])

        # Check client's subscriptions
        assert manager.connections[mock_websocket] == {1, 2, 3}

        # Check subscriber lists
        assert mock_websocket in manager.subscribers[1]
        assert mock_websocket in manager.subscribers[2]
        assert mock_websocket in manager.subscribers[3]

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, manager, mock_websocket):
        """Test subscribe when not connected (should be ignored)."""
        await manager.subscribe(mock_websocket, [1, 2, 3])

        # Should not create subscriptions
        assert mock_websocket not in manager.connections
        assert 1 not in manager.subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe(self, manager, mock_websocket):
        """Test unsubscribing from starlistings."""
        # Setup
        manager.connections[mock_websocket] = {1, 2, 3}
        manager.subscribers[1] = {mock_websocket}
        manager.subscribers[2] = {mock_websocket}
        manager.subscribers[3] = {mock_websocket}

        # Unsubscribe from some
        await manager.unsubscribe(mock_websocket, [1, 2])

        # Check remaining subscriptions
        assert manager.connections[mock_websocket] == {3}
        assert 1 not in manager.subscribers
        assert 2 not in manager.subscribers
        assert mock_websocket in manager.subscribers[3]

    @pytest.mark.asyncio
    async def test_unsubscribe_cleans_empty_sets(self, manager, mock_websocket):
        """Test that unsubscribe cleans up empty subscriber sets."""
        manager.connections[mock_websocket] = {1}
        manager.subscribers[1] = {mock_websocket}

        await manager.unsubscribe(mock_websocket, [1])

        # Empty set should be cleaned up
        assert 1 not in manager.subscribers

    def test_get_subscriptions(self, manager, mock_websocket):
        """Test getting subscriptions for a client."""
        manager.connections[mock_websocket] = {1, 2, 3}

        subscriptions = manager.get_subscriptions(mock_websocket)

        assert subscriptions == {1, 2, 3}

    def test_get_subscriptions_not_connected(self, manager, mock_websocket):
        """Test getting subscriptions for non-connected client."""
        subscriptions = manager.get_subscriptions(mock_websocket)

        assert subscriptions == set()

    def test_get_subscriber_count(self, manager, mock_websocket):
        """Test getting subscriber count for a starlisting."""
        # Create multiple websockets
        ws1 = MagicMock()
        ws2 = MagicMock()
        ws3 = MagicMock()

        manager.subscribers[1] = {ws1, ws2, ws3}

        count = manager.get_subscriber_count(1)

        assert count == 3

    def test_get_subscriber_count_no_subscribers(self, manager):
        """Test getting subscriber count when no subscribers."""
        count = manager.get_subscriber_count(999)

        assert count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, manager):
        """Test broadcasting message to subscribers."""
        # Create multiple websockets
        ws1 = MagicMock()
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.send_text = AsyncMock()

        manager.connections[ws1] = {1}
        manager.connections[ws2] = {1}
        manager.subscribers[1] = {ws1, ws2}

        message = {"type": "candle", "data": "test"}

        sent_count = await manager.broadcast_to_subscribers(1, message)

        assert sent_count == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers_no_subscribers(self, manager):
        """Test broadcasting when no subscribers."""
        message = {"type": "candle", "data": "test"}

        sent_count = await manager.broadcast_to_subscribers(999, message)

        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_failed_send(self, manager):
        """Test that broadcast handles failed sends gracefully."""
        # Create websockets - one will fail
        ws1 = MagicMock()
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.send_text = AsyncMock(side_effect=Exception("Send failed"))

        manager.connections[ws1] = {1}
        manager.connections[ws2] = {1}
        manager.subscribers[1] = {ws1, ws2}

        message = {"type": "candle", "data": "test"}

        sent_count = await manager.broadcast_to_subscribers(1, message)

        # Should send to one, fail on other
        assert sent_count == 1
        # Failed connection should be cleaned up
        assert ws2 not in manager.connections

    @pytest.mark.asyncio
    async def test_send_to_client_success(self, manager, mock_websocket):
        """Test sending message to specific client."""
        manager.connections[mock_websocket] = set()

        message = {"type": "success", "message": "test"}

        result = await manager.send_to_client(mock_websocket, message)

        assert result is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_client_failure(self, manager, mock_websocket):
        """Test sending message failure handling."""
        manager.connections[mock_websocket] = set()
        mock_websocket.send_text.side_effect = Exception("Send failed")

        # Mock heartbeat task
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        manager._heartbeat_tasks[mock_websocket] = mock_task

        message = {"type": "success", "message": "test"}

        result = await manager.send_to_client(mock_websocket, message)

        assert result is False
        # Connection should be cleaned up
        assert mock_websocket not in manager.connections
