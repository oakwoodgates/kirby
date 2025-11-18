"""
API router for funding rate and open interest endpoints.

All endpoints require authentication via API key (X-API-Key header).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user, AuthenticatedUser
from src.db.models import Coin, Exchange, MarketType, QuoteCurrency, Starlisting
from src.db.repositories import FundingRateRepository, OpenInterestRepository
from src.schemas.funding import (
    FundingRateListResponse,
    FundingRateMetadata,
    FundingRateResponse,
    OpenInterestListResponse,
    OpenInterestMetadata,
    OpenInterestResponse,
)

router = APIRouter(tags=["funding"])


@router.get(
    "/funding/{exchange}/{coin}/{quote}/{market_type}",
    response_model=FundingRateListResponse,
    summary="Get funding rate data",
    description="Retrieve funding rate data for a specific perpetual trading pair",
)
async def get_funding_rates(
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    start_time: datetime | None = Query(None, description="Start time (ISO 8601 or Unix timestamp)"),
    end_time: datetime | None = Query(None, description="End time (ISO 8601 or Unix timestamp)"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FundingRateListResponse:
    """
    Get funding rate data for a perpetual trading pair.

    Parameters:
    - **exchange**: Exchange name (e.g., 'hyperliquid')
    - **coin**: Base asset symbol (e.g., 'BTC')
    - **quote**: Quote asset symbol (e.g., 'USD')
    - **market_type**: Market type (e.g., 'perps')
    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter
    - **limit**: Maximum number of records (default: 1000, max: 5000)

    Returns:
    - List of funding rates with metadata
    """
    # Find starlisting by components - just get the ID and active status
    # Avoid loading relationships to prevent greenlet errors
    # Note: We query for any interval since funding rates are the same across intervals
    stmt = (
        select(Starlisting.id, Starlisting.active)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .where(
            Exchange.name == exchange,
            Coin.symbol == coin.upper(),
            QuoteCurrency.symbol == quote.upper(),
            MarketType.name == market_type,
        )
        .limit(1)  # Get any one starlisting for this trading pair
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Trading pair not found: {exchange}/{coin}/{quote}/{market_type}",
        )

    starlisting_id, is_active = row

    if not is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Trading pair is not active: {exchange}/{coin}/{quote}/{market_type}",
        )

    # Get funding rates using repository
    funding_repo = FundingRateRepository(pool=None)  # Pool not needed for query with session
    funding_rates = await funding_repo.get_funding_rates(
        session=session,
        starlisting_id=starlisting_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    # Convert to response models (manually to avoid lazy loading)
    funding_responses = [
        FundingRateResponse(
            time=rate.time,
            funding_rate=rate.funding_rate,
            premium=rate.premium,
            mark_price=rate.mark_price,
            index_price=rate.index_price,
            oracle_price=rate.oracle_price,
            mid_price=rate.mid_price,
            next_funding_time=rate.next_funding_time,
        )
        for rate in funding_rates
    ]

    # Build metadata using URL parameters
    metadata = FundingRateMetadata(
        exchange=exchange,
        coin=coin.upper(),
        quote=quote.upper(),
        trading_pair=f"{coin.upper()}/{quote.upper()}",
        market_type=market_type,
        count=len(funding_responses),
        start_time=start_time,
        end_time=end_time,
    )

    return FundingRateListResponse(data=funding_responses, metadata=metadata)


@router.get(
    "/open-interest/{exchange}/{coin}/{quote}/{market_type}",
    response_model=OpenInterestListResponse,
    summary="Get open interest data",
    description="Retrieve open interest data for a specific perpetual trading pair",
)
async def get_open_interest(
    exchange: str,
    coin: str,
    quote: str,
    market_type: str,
    start_time: datetime | None = Query(None, description="Start time (ISO 8601 or Unix timestamp)"),
    end_time: datetime | None = Query(None, description="End time (ISO 8601 or Unix timestamp)"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> OpenInterestListResponse:
    """
    Get open interest data for a perpetual trading pair.

    Parameters:
    - **exchange**: Exchange name (e.g., 'hyperliquid')
    - **coin**: Base asset symbol (e.g., 'BTC')
    - **quote**: Quote asset symbol (e.g., 'USD')
    - **market_type**: Market type (e.g., 'perps')
    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter
    - **limit**: Maximum number of records (default: 1000, max: 5000)

    Returns:
    - List of open interest snapshots with metadata
    """
    # Find starlisting by components - just get the ID and active status
    # Avoid loading relationships to prevent greenlet errors
    # Note: We query for any interval since OI is the same across intervals
    stmt = (
        select(Starlisting.id, Starlisting.active)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .where(
            Exchange.name == exchange,
            Coin.symbol == coin.upper(),
            QuoteCurrency.symbol == quote.upper(),
            MarketType.name == market_type,
        )
        .limit(1)  # Get any one starlisting for this trading pair
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Trading pair not found: {exchange}/{coin}/{quote}/{market_type}",
        )

    starlisting_id, is_active = row

    if not is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Trading pair is not active: {exchange}/{coin}/{quote}/{market_type}",
        )

    # Get open interest using repository
    oi_repo = OpenInterestRepository(pool=None)  # Pool not needed for query with session
    oi_records = await oi_repo.get_open_interest(
        session=session,
        starlisting_id=starlisting_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    # Convert to response models (manually to avoid lazy loading)
    oi_responses = [
        OpenInterestResponse(
            time=record.time,
            open_interest=record.open_interest,
            notional_value=record.notional_value,
            day_base_volume=record.day_base_volume,
            day_notional_volume=record.day_notional_volume,
        )
        for record in oi_records
    ]

    # Build metadata using URL parameters
    metadata = OpenInterestMetadata(
        exchange=exchange,
        coin=coin.upper(),
        quote=quote.upper(),
        trading_pair=f"{coin.upper()}/{quote.upper()}",
        market_type=market_type,
        count=len(oi_responses),
        start_time=start_time,
        end_time=end_time,
    )

    return OpenInterestListResponse(data=oi_responses, metadata=metadata)
