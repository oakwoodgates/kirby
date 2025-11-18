"""WebSocket API router for real-time candle streaming.

This router provides a WebSocket endpoint (/ws) that allows clients to subscribe to
real-time candle updates. Clients can subscribe to multiple starlistings and optionally
request historical data on connection.

Authentication is required via API key passed as query parameter: ws://host/ws?api_key=kb_xxx
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import select
from structlog import get_logger

from src.api.dependencies import get_db_session
from src.api.middleware.auth import validate_api_key
from src.api.websocket_manager import ConnectionManager
from src.db.models import APIKey, Candle, Coin, Exchange, Interval, MarketType, QuoteCurrency, Starlisting, User
from src.schemas.candles import CandleResponse
from src.schemas.websocket import (
    WebSocketErrorMessage,
    WebSocketHistoricalDataMessage,
    WebSocketPingMessage,
    WebSocketPongMessage,
    WebSocketSubscribeMessage,
    WebSocketSuccessMessage,
    WebSocketUnsubscribeMessage,
)

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])

# Global connection manager (initialized in main.py)
connection_manager: ConnectionManager | None = None


def set_connection_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager.

    This is called from main.py during app initialization.

    Args:
        manager: The ConnectionManager instance to use
    """
    global connection_manager
    connection_manager = manager


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time candle streaming.

    Authentication:
    - Required: API key as query parameter (e.g., ws://host/ws?api_key=kb_xxx)
    - Connection will be rejected if API key is invalid, expired, or inactive

    Protocol:
    - Client connects: ws://host/ws?api_key=kb_xxx
    - Client sends: {"action": "subscribe", "starlisting_ids": [1, 2, 3], "history": 100}
    - Server sends: {"type": "success", "message": "Subscribed to 3 starlistings"}
    - Server sends: {"type": "historical", "starlisting_id": 1, "data": [...]}
    - Server sends: {"type": "candle", "starlisting_id": 1, "data": {...}}
    - Client sends: {"action": "unsubscribe", "starlisting_ids": [1]}
    - Client sends: {"action": "ping"}
    - Server sends: {"type": "pong", "timestamp": "2025-11-17T10:00:00Z"}

    Args:
        websocket: The WebSocket connection
    """
    if connection_manager is None:
        logger.error("websocket_connection_manager_not_initialized")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # Check capacity before accepting
    if connection_manager.is_at_capacity:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Server at capacity",
        )
        logger.warning("websocket_connection_rejected_capacity")
        return

    # Authenticate via API key from query parameter
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing API key (use ?api_key=kb_xxx)",
        )
        logger.warning("websocket_connection_rejected_no_api_key")
        return

    # Validate API key
    user: User | None = None
    api_key_obj: APIKey | None = None

    async for session in get_db_session():
        try:
            user, api_key_obj = await validate_api_key(session, api_key)
        except Exception as e:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Authentication failed: {str(e)}",
            )
            logger.warning("websocket_connection_rejected_invalid_api_key", error=str(e))
            return
        finally:
            await session.close()

    # Accept connection
    accepted = await connection_manager.connect(websocket)
    if not accepted:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Connection rejected",
        )
        return

    logger.info(
        "websocket_authenticated_connection",
        user_id=user.id,
        username=user.username,
        api_key_id=api_key_obj.id,
    )

    try:
        # Main message loop
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    await handle_subscribe(websocket, message)
                elif action == "unsubscribe":
                    await handle_unsubscribe(websocket, message)
                elif action == "ping":
                    await handle_ping(websocket, message)
                else:
                    await send_error(
                        websocket,
                        f"Unknown action: {action}",
                        "unknown_action",
                    )

            except json.JSONDecodeError:
                await send_error(websocket, "Invalid JSON", "invalid_json")
            except ValidationError as e:
                await send_error(
                    websocket,
                    f"Validation error: {str(e)}",
                    "validation_error",
                )
            except Exception as e:
                logger.error(
                    "websocket_message_handler_error",
                    error=str(e),
                )
                await send_error(
                    websocket,
                    "Internal server error",
                    "internal_error",
                )

    except WebSocketDisconnect:
        logger.info("websocket_client_disconnected")
    except Exception as e:
        logger.error("websocket_connection_error", error=str(e))
    finally:
        # Clean up connection
        await connection_manager.disconnect(websocket)


async def handle_subscribe(websocket: WebSocket, message: Dict[str, Any]) -> None:
    """Handle subscribe action.

    Args:
        websocket: The WebSocket connection
        message: The subscribe message dict
    """
    # Validate message
    try:
        subscribe_msg = WebSocketSubscribeMessage(**message)
    except ValidationError as e:
        await send_error(websocket, str(e), "validation_error")
        return

    # Validate starlistings exist and are active
    valid_starlisting_ids = []
    invalid_starlisting_ids = []

    async for session in get_db_session():
        try:
            for starlisting_id in subscribe_msg.starlisting_ids:
                # Check if starlisting exists and is active
                stmt = select(Starlisting.id, Starlisting.active).where(
                    Starlisting.id == starlisting_id
                )
                result = await session.execute(stmt)
                row = result.one_or_none()

                if not row:
                    invalid_starlisting_ids.append(starlisting_id)
                elif not row[1]:  # not active
                    invalid_starlisting_ids.append(starlisting_id)
                else:
                    valid_starlisting_ids.append(starlisting_id)
        finally:
            await session.close()

    # Send error if any invalid starlistings
    if invalid_starlisting_ids:
        await send_error(
            websocket,
            f"Invalid or inactive starlisting IDs: {invalid_starlisting_ids}",
            "invalid_starlisting",
        )
        # Don't proceed if any are invalid
        return

    # Subscribe to valid starlistings
    await connection_manager.subscribe(websocket, valid_starlisting_ids)

    # Send success confirmation
    success_msg = WebSocketSuccessMessage(
        type="success",
        message=f"Subscribed to {len(valid_starlisting_ids)} starlisting(s)",
        starlisting_ids=valid_starlisting_ids,
    )
    await connection_manager.send_to_client(websocket, success_msg.model_dump())

    # Send historical data if requested
    if subscribe_msg.history and subscribe_msg.history > 0:
        await send_historical_data(websocket, valid_starlisting_ids, subscribe_msg.history)


async def handle_unsubscribe(websocket: WebSocket, message: Dict[str, Any]) -> None:
    """Handle unsubscribe action.

    Args:
        websocket: The WebSocket connection
        message: The unsubscribe message dict
    """
    # Validate message
    try:
        unsubscribe_msg = WebSocketUnsubscribeMessage(**message)
    except ValidationError as e:
        await send_error(websocket, str(e), "validation_error")
        return

    # Unsubscribe from starlistings
    await connection_manager.unsubscribe(websocket, unsubscribe_msg.starlisting_ids)

    # Send success confirmation
    success_msg = WebSocketSuccessMessage(
        type="success",
        message=f"Unsubscribed from {len(unsubscribe_msg.starlisting_ids)} starlisting(s)",
        starlisting_ids=unsubscribe_msg.starlisting_ids,
    )
    await connection_manager.send_to_client(websocket, success_msg.model_dump())


async def handle_ping(websocket: WebSocket, message: Dict[str, Any]) -> None:
    """Handle ping action.

    Args:
        websocket: The WebSocket connection
        message: The ping message dict
    """
    # Validate message
    try:
        WebSocketPingMessage(**message)
    except ValidationError as e:
        await send_error(websocket, str(e), "validation_error")
        return

    # Send pong response
    pong_msg = WebSocketPongMessage(
        type="pong",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    await connection_manager.send_to_client(websocket, pong_msg.model_dump())


async def send_error(websocket: WebSocket, message: str, code: str) -> None:
    """Send an error message to the client.

    Args:
        websocket: The WebSocket connection
        message: Error message
        code: Error code
    """
    error_msg = WebSocketErrorMessage(
        type="error",
        message=message,
        code=code,
    )
    await connection_manager.send_to_client(websocket, error_msg.model_dump())


async def send_historical_data(
    websocket: WebSocket, starlisting_ids: list[int], limit: int
) -> None:
    """Query and send historical candle data for subscribed starlistings.

    Args:
        websocket: The WebSocket connection
        starlisting_ids: List of starlisting IDs to fetch history for
        limit: Number of historical candles to fetch
    """
    async for session in get_db_session():
        try:
            for starlisting_id in starlisting_ids:
                # Query historical candles with starlisting metadata
                stmt = (
                    select(
                        Candle.time,
                        Candle.open,
                        Candle.high,
                        Candle.low,
                        Candle.close,
                        Candle.volume,
                        Candle.num_trades,
                        Starlisting.id,
                        Exchange.name.label("exchange"),
                        Coin.symbol.label("coin"),
                        QuoteCurrency.symbol.label("quote"),
                        MarketType.name.label("market_type"),
                        Interval.name.label("interval"),
                    )
                    .join(Starlisting, Candle.starlisting_id == Starlisting.id)
                    .join(Exchange, Starlisting.exchange_id == Exchange.id)
                    .join(Coin, Starlisting.coin_id == Coin.id)
                    .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
                    .join(MarketType, Starlisting.market_type_id == MarketType.id)
                    .join(Interval, Starlisting.interval_id == Interval.id)
                    .where(Candle.starlisting_id == starlisting_id)
                    .order_by(Candle.time.desc())
                    .limit(limit)
                )

                result = await session.execute(stmt)
                rows = result.all()

                if not rows:
                    # No historical data available
                    continue

                # Reverse to get chronological order (oldest first)
                rows = list(reversed(rows))

                # Build candle response objects
                candles = []
                for row in rows:
                    candle = CandleResponse(
                        time=row.time,
                        open=row.open,
                        high=row.high,
                        low=row.low,
                        close=row.close,
                        volume=row.volume,
                        num_trades=row.num_trades,
                    )
                    candles.append(candle)

                # Get metadata from first row
                first_row = rows[0]
                trading_pair = f"{first_row.coin}/{first_row.quote}"

                # Build historical data message
                historical_msg = WebSocketHistoricalDataMessage(
                    type="historical",
                    starlisting_id=starlisting_id,
                    exchange=first_row.exchange,
                    coin=first_row.coin,
                    quote=first_row.quote,
                    trading_pair=trading_pair,
                    market_type=first_row.market_type,
                    interval=first_row.interval,
                    count=len(candles),
                    data=candles,
                )

                # Send to client
                await connection_manager.send_to_client(
                    websocket, historical_msg.model_dump(mode="json")
                )

                logger.debug(
                    "sent_historical_data",
                    starlisting_id=starlisting_id,
                    count=len(candles),
                )

        except Exception as e:
            logger.error(
                "send_historical_data_error",
                starlisting_ids=starlisting_ids,
                error=str(e),
            )
            await send_error(
                websocket,
                "Failed to fetch historical data",
                "historical_data_error",
            )
        finally:
            await session.close()
