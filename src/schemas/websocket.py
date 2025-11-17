"""Pydantic schemas for WebSocket API messages.

These schemas define the structure and validation rules for WebSocket messages
exchanged between clients and the server.
"""

from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.candles import CandleResponse


class WebSocketSubscribeMessage(BaseModel):
    """Client message to subscribe to starlisting updates.

    Example:
        {
            "action": "subscribe",
            "starlisting_ids": [1, 2, 3],
            "history": 100
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "subscribe",
                "starlisting_ids": [1, 2, 3],
                "history": 100,
            }
        }
    )

    action: Literal["subscribe"] = Field(..., description="Action type (must be 'subscribe')")
    starlisting_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of starlisting IDs to subscribe to (1-100)",
    )
    history: int | None = Field(
        None,
        ge=0,
        le=1000,
        description="Optional: Number of historical candles to send (0-1000)",
    )

    @field_validator("starlisting_ids")
    @classmethod
    def validate_starlisting_ids(cls, v: list[int]) -> list[int]:
        """Validate starlisting IDs are positive integers."""
        if not all(sid > 0 for sid in v):
            raise ValueError("All starlisting IDs must be positive integers")
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for sid in v:
            if sid not in seen:
                seen.add(sid)
                unique_ids.append(sid)
        return unique_ids


class WebSocketUnsubscribeMessage(BaseModel):
    """Client message to unsubscribe from starlisting updates.

    Example:
        {
            "action": "unsubscribe",
            "starlisting_ids": [1]
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "unsubscribe",
                "starlisting_ids": [1],
            }
        }
    )

    action: Literal["unsubscribe"] = Field(
        ..., description="Action type (must be 'unsubscribe')"
    )
    starlisting_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of starlisting IDs to unsubscribe from (1-100)",
    )

    @field_validator("starlisting_ids")
    @classmethod
    def validate_starlisting_ids(cls, v: list[int]) -> list[int]:
        """Validate starlisting IDs are positive integers."""
        if not all(sid > 0 for sid in v):
            raise ValueError("All starlisting IDs must be positive integers")
        return list(set(v))  # Remove duplicates


class WebSocketPingMessage(BaseModel):
    """Client message to ping the server (keepalive).

    Example:
        {
            "action": "ping"
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "ping",
            }
        }
    )

    action: Literal["ping"] = Field(..., description="Action type (must be 'ping')")


class WebSocketPongMessage(BaseModel):
    """Server response to ping message.

    Example:
        {
            "type": "pong",
            "timestamp": "2025-11-17T10:00:00Z"
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "pong",
                "timestamp": "2025-11-17T10:00:00Z",
            }
        }
    )

    type: Literal["pong"] = Field(..., description="Message type")
    timestamp: str = Field(..., description="Server timestamp (ISO 8601)")


class WebSocketErrorMessage(BaseModel):
    """Server error message.

    Example:
        {
            "type": "error",
            "message": "Invalid starlisting_id: 999",
            "code": "invalid_starlisting"
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "error",
                "message": "Invalid starlisting_id: 999",
                "code": "invalid_starlisting",
            }
        }
    )

    type: Literal["error"] = Field(..., description="Message type")
    message: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Optional error code")


class WebSocketSuccessMessage(BaseModel):
    """Server success confirmation message.

    Example:
        {
            "type": "success",
            "message": "Subscribed to 3 starlistings",
            "starlisting_ids": [1, 2, 3]
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "success",
                "message": "Subscribed to 3 starlistings",
                "starlisting_ids": [1, 2, 3],
            }
        }
    )

    type: Literal["success"] = Field(..., description="Message type")
    message: str = Field(..., description="Success message")
    starlisting_ids: list[int] | None = Field(
        None, description="Optional list of affected starlisting IDs"
    )


class WebSocketCandleMessage(BaseModel):
    """Server message with candle update.

    This matches the format from the PostgreSQL listener and REST API.

    Example:
        {
            "type": "candle",
            "starlisting_id": 1,
            "exchange": "hyperliquid",
            "coin": "BTC",
            "quote": "USD",
            "trading_pair": "BTC/USD",
            "market_type": "perps",
            "interval": "1m",
            "data": {
                "time": "2025-11-17T10:00:00Z",
                "open": "67500.50",
                "high": "67800.00",
                "low": "67400.25",
                "close": "67650.75",
                "volume": "1234.56",
                "num_trades": 542
            }
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "candle",
                "starlisting_id": 1,
                "exchange": "hyperliquid",
                "coin": "BTC",
                "quote": "USD",
                "trading_pair": "BTC/USD",
                "market_type": "perps",
                "interval": "1m",
                "data": {
                    "time": "2025-11-17T10:00:00Z",
                    "open": "67500.50",
                    "high": "67800.00",
                    "low": "67400.25",
                    "close": "67650.75",
                    "volume": "1234.56",
                    "num_trades": 542,
                },
            }
        }
    )

    type: Literal["candle"] = Field(..., description="Message type")
    starlisting_id: int = Field(..., description="Starlisting ID")
    exchange: str = Field(..., description="Exchange name")
    coin: str = Field(..., description="Base asset symbol")
    quote: str = Field(..., description="Quote asset symbol")
    trading_pair: str = Field(..., description="Trading pair (e.g., BTC/USD)")
    market_type: str = Field(..., description="Market type")
    interval: str = Field(..., description="Time interval")
    data: CandleResponse = Field(..., description="Candle data")


class WebSocketHistoricalDataMessage(BaseModel):
    """Server message with historical candles for initial subscription.

    Example:
        {
            "type": "historical",
            "starlisting_id": 1,
            "exchange": "hyperliquid",
            "coin": "BTC",
            "quote": "USD",
            "trading_pair": "BTC/USD",
            "market_type": "perps",
            "interval": "1m",
            "count": 100,
            "data": [
                {
                    "time": "2025-11-17T09:00:00Z",
                    "open": "67400.00",
                    ...
                },
                ...
            ]
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "historical",
                "starlisting_id": 1,
                "exchange": "hyperliquid",
                "coin": "BTC",
                "quote": "USD",
                "trading_pair": "BTC/USD",
                "market_type": "perps",
                "interval": "1m",
                "count": 100,
                "data": [],
            }
        }
    )

    type: Literal["historical"] = Field(..., description="Message type")
    starlisting_id: int = Field(..., description="Starlisting ID")
    exchange: str = Field(..., description="Exchange name")
    coin: str = Field(..., description="Base asset symbol")
    quote: str = Field(..., description="Quote asset symbol")
    trading_pair: str = Field(..., description="Trading pair (e.g., BTC/USD)")
    market_type: str = Field(..., description="Market type")
    interval: str = Field(..., description="Time interval")
    count: int = Field(..., description="Number of candles in data")
    data: list[CandleResponse] = Field(..., description="Historical candle data")
