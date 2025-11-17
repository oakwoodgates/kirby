"""WebSocket connection manager for real-time candle streaming.

This module manages active WebSocket connections, subscriptions, and message broadcasting
to clients. It tracks which clients are subscribed to which starlistings and efficiently
routes real-time updates to only the relevant subscribers.

Features:
- Connection tracking and lifecycle management
- Subscription management (subscribe/unsubscribe to starlistings)
- Heartbeat/ping mechanism to keep connections alive
- Broadcast to specific subscribers based on starlisting_id
- Connection limits and error handling
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Set

from fastapi import WebSocket
from structlog import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and subscriptions for real-time streaming.

    This class maintains two key data structures:
    1. connections: Maps WebSocket -> Set of starlisting_ids the client is subscribed to
    2. subscribers: Maps starlisting_id -> Set of WebSockets subscribed to it

    The dual mapping enables efficient operations in both directions:
    - Find all subscriptions for a client (for disconnect cleanup)
    - Find all clients subscribed to a starlisting (for broadcasting)
    """

    def __init__(self, max_connections: int = 100, heartbeat_interval: int = 30):
        """Initialize the connection manager.

        Args:
            max_connections: Maximum number of concurrent WebSocket connections
            heartbeat_interval: Seconds between heartbeat pings
        """
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval

        # WebSocket -> Set of starlisting_ids
        self.connections: Dict[WebSocket, Set[int]] = {}

        # starlisting_id -> Set of WebSockets
        self.subscribers: Dict[int, Set[WebSocket]] = defaultdict(set)

        # Active heartbeat tasks (one per WebSocket)
        self._heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}

        logger.info(
            "connection_manager_initialized",
            max_connections=max_connections,
            heartbeat_interval=heartbeat_interval,
        )

    @property
    def connection_count(self) -> int:
        """Get current number of active connections."""
        return len(self.connections)

    @property
    def is_at_capacity(self) -> bool:
        """Check if connection limit is reached."""
        return self.connection_count >= self.max_connections

    async def connect(self, websocket: WebSocket) -> bool:
        """Register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register

        Returns:
            True if connection was accepted, False if at capacity
        """
        if self.is_at_capacity:
            logger.warning(
                "connection_rejected_capacity",
                current_count=self.connection_count,
                max_connections=self.max_connections,
            )
            return False

        # Accept the WebSocket connection
        await websocket.accept()

        # Initialize empty subscription set for this connection
        self.connections[websocket] = set()

        # Start heartbeat task for this connection
        self._heartbeat_tasks[websocket] = asyncio.create_task(
            self._heartbeat_loop(websocket)
        )

        logger.info(
            "websocket_connected",
            total_connections=self.connection_count,
        )

        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection and clean up subscriptions.

        Args:
            websocket: The WebSocket connection to remove
        """
        if websocket not in self.connections:
            return

        # Cancel heartbeat task
        if websocket in self._heartbeat_tasks:
            self._heartbeat_tasks[websocket].cancel()
            del self._heartbeat_tasks[websocket]

        # Get all starlistings this client was subscribed to
        starlisting_ids = self.connections[websocket]

        # Remove client from all subscription lists
        for starlisting_id in starlisting_ids:
            if starlisting_id in self.subscribers:
                self.subscribers[starlisting_id].discard(websocket)

                # Clean up empty subscriber sets
                if not self.subscribers[starlisting_id]:
                    del self.subscribers[starlisting_id]

        # Remove connection
        del self.connections[websocket]

        logger.info(
            "websocket_disconnected",
            total_connections=self.connection_count,
            unsubscribed_from=len(starlisting_ids),
        )

    async def subscribe(self, websocket: WebSocket, starlisting_ids: list[int]) -> None:
        """Subscribe a client to one or more starlistings.

        Args:
            websocket: The WebSocket connection
            starlisting_ids: List of starlisting IDs to subscribe to
        """
        if websocket not in self.connections:
            logger.warning("subscribe_failed_not_connected")
            return

        for starlisting_id in starlisting_ids:
            # Add to client's subscription set
            self.connections[websocket].add(starlisting_id)

            # Add client to starlisting's subscriber set
            self.subscribers[starlisting_id].add(websocket)

        logger.info(
            "websocket_subscribed",
            starlisting_ids=starlisting_ids,
            total_subscriptions=len(self.connections[websocket]),
        )

    async def unsubscribe(
        self, websocket: WebSocket, starlisting_ids: list[int]
    ) -> None:
        """Unsubscribe a client from one or more starlistings.

        Args:
            websocket: The WebSocket connection
            starlisting_ids: List of starlisting IDs to unsubscribe from
        """
        if websocket not in self.connections:
            logger.warning("unsubscribe_failed_not_connected")
            return

        for starlisting_id in starlisting_ids:
            # Remove from client's subscription set
            self.connections[websocket].discard(starlisting_id)

            # Remove client from starlisting's subscriber set
            if starlisting_id in self.subscribers:
                self.subscribers[starlisting_id].discard(websocket)

                # Clean up empty subscriber sets
                if not self.subscribers[starlisting_id]:
                    del self.subscribers[starlisting_id]

        logger.info(
            "websocket_unsubscribed",
            starlisting_ids=starlisting_ids,
            remaining_subscriptions=len(self.connections[websocket]),
        )

    def get_subscriptions(self, websocket: WebSocket) -> Set[int]:
        """Get all starlisting IDs a client is subscribed to.

        Args:
            websocket: The WebSocket connection

        Returns:
            Set of starlisting IDs (empty if not connected)
        """
        return self.connections.get(websocket, set())

    def get_subscriber_count(self, starlisting_id: int) -> int:
        """Get number of clients subscribed to a starlisting.

        Args:
            starlisting_id: The starlisting ID

        Returns:
            Number of subscribed clients
        """
        return len(self.subscribers.get(starlisting_id, set()))

    async def broadcast_to_subscribers(
        self, starlisting_id: int, message: Dict[str, Any]
    ) -> int:
        """Broadcast a message to all clients subscribed to a starlisting.

        Args:
            starlisting_id: The starlisting ID
            message: The message to broadcast (will be JSON serialized)

        Returns:
            Number of clients the message was sent to
        """
        if starlisting_id not in self.subscribers:
            return 0

        # Get all subscribers for this starlisting
        subscribers = self.subscribers[starlisting_id].copy()

        # Serialize message once (more efficient than per-client)
        message_json = json.dumps(message)

        # Track successful sends
        sent_count = 0
        failed_websockets = []

        # Broadcast to all subscribers
        for websocket in subscribers:
            try:
                await websocket.send_text(message_json)
                sent_count += 1
            except Exception as e:
                logger.error(
                    "broadcast_send_failed",
                    starlisting_id=starlisting_id,
                    error=str(e),
                )
                # Mark for cleanup
                failed_websockets.append(websocket)

        # Clean up failed connections
        for websocket in failed_websockets:
            await self.disconnect(websocket)

        if sent_count > 0:
            logger.debug(
                "broadcast_sent",
                starlisting_id=starlisting_id,
                sent_count=sent_count,
                failed_count=len(failed_websockets),
            )

        return sent_count

    async def send_to_client(
        self, websocket: WebSocket, message: Dict[str, Any]
    ) -> bool:
        """Send a message to a specific client.

        Args:
            websocket: The WebSocket connection
            message: The message to send (will be JSON serialized)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message_json = json.dumps(message)
            await websocket.send_text(message_json)
            return True
        except Exception as e:
            logger.error(
                "send_to_client_failed",
                error=str(e),
            )
            # Clean up failed connection
            await self.disconnect(websocket)
            return False

    async def _heartbeat_loop(self, websocket: WebSocket) -> None:
        """Background task that sends periodic pings to keep connection alive.

        Args:
            websocket: The WebSocket connection
        """
        try:
            while websocket in self.connections:
                await asyncio.sleep(self.heartbeat_interval)

                # Send ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                success = await self.send_to_client(websocket, ping_message)
                if not success:
                    # Connection failed, task will be cancelled in disconnect()
                    break

        except asyncio.CancelledError:
            # Normal shutdown
            pass
        except Exception as e:
            logger.error(
                "heartbeat_loop_error",
                error=str(e),
            )
            await self.disconnect(websocket)
