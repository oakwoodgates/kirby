"""
API router for candle data endpoints.

All endpoints require authentication via API key (X-API-Key header).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user, AuthenticatedUser
from src.db.models import Coin, Exchange, Interval, MarketType, QuoteCurrency, Starlisting
from src.db.repositories import CandleRepository
from src.schemas.candles import CandleListResponse, CandleMetadata, CandleResponse

router = APIRouter(prefix="/candles", tags=["candles"])


@router.get(
    "/{exchange}/{coin}/{quote}/{market_type}/{interval}",
    response_model=CandleListResponse,
    summary="Get candle data",
    description="Retrieve OHLCV candle data for a specific trading pair and interval",
)
async def get_candles(
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    interval: str,
    start_time: datetime | None = Query(None, description="Start time (ISO 8601 or Unix timestamp)"),
    end_time: datetime | None = Query(None, description="End time (ISO 8601 or Unix timestamp)"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of candles to return"),
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CandleListResponse:
    """
    Get candle data for a trading pair.

    Parameters:
    - **exchange**: Exchange name (e.g., 'hyperliquid')
    - **coin**: Base asset symbol (e.g., 'BTC')
    - **quote**: Quote asset symbol (e.g., 'USD')
    - **market_type**: Market type (e.g., 'perps', 'spot')
    - **interval**: Time interval (e.g., '1m', '15m', '4h', '1d')
    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter
    - **limit**: Maximum number of candles (default: 1000, max: 5000)

    Returns:
    - List of candles with metadata
    """
    # Find starlisting by components - just get the ID and active status
    # Avoid loading relationships to prevent greenlet errors
    stmt = (
        select(Starlisting.id, Starlisting.active)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .join(Interval, Starlisting.interval_id == Interval.id)
        .where(
            Exchange.name == exchange,
            Coin.symbol == coin.upper(),
            QuoteCurrency.symbol == quote.upper(),
            MarketType.name == market_type,
            Interval.name == interval,
        )
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Starlisting not found: {exchange}/{coin}/{quote}/{market_type}/{interval}",
        )

    starlisting_id, is_active = row

    if not is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Starlisting is not active: {exchange}/{coin}/{quote}/{market_type}/{interval}",
        )

    # Get candles using repository with session-based query
    candle_repo = CandleRepository(pool=None)  # Pool not needed for get_candles with session
    candles = await candle_repo.get_candles(
        session=session,
        starlisting_id=starlisting_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    # Convert to response models (manually to avoid lazy loading the starlisting relationship)
    candle_responses = [
        CandleResponse(
            time=candle.time,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            num_trades=candle.num_trades,
        )
        for candle in candles
    ]

    # Build metadata using URL parameters (avoids accessing starlisting relationships)
    metadata = CandleMetadata(
        exchange=exchange,
        coin=coin.upper(),
        quote=quote.upper(),
        trading_pair=f"{coin.upper()}/{quote.upper()}",
        market_type=market_type,
        interval=interval,
        count=len(candle_responses),
        start_time=start_time,
        end_time=end_time,
    )

    return CandleListResponse(data=candle_responses, metadata=metadata)
