"""
Candles (OHLCV) API endpoints.
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.candle import Candle
from src.schemas.candle import CandleResponse

router = APIRouter()


@router.get("/candles", response_model=List[CandleResponse])
async def get_candles(
    listing_id: int = Query(..., description="Listing ID to query"),
    interval: str = Query("1m", description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601 format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of candles to return"),
    offset: int = Query(0, ge=0, description="Number of candles to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[CandleResponse]:
    """
    Query candles (OHLCV data) with filters.

    **Query Parameters:**
    - `listing_id`: Listing ID (required)
    - `interval`: Candle interval (default: 1m)
    - `start_date`: Start timestamp (optional, ISO 8601)
    - `end_date`: End timestamp (optional, ISO 8601)
    - `limit`: Maximum results (default: 1000, max: 10000)
    - `offset`: Skip N records (default: 0)

    **Returns:**
    - List of candles ordered by timestamp (newest first)

    **Example:**
    ```
    GET /api/v1/candles?listing_id=1&interval=1m&limit=100
    ```
    """
    try:
        # Build query
        query = select(Candle).where(
            Candle.listing_id == listing_id,
            Candle.interval == interval
        )

        # Apply date filters
        if start_date:
            query = query.where(Candle.timestamp >= start_date)
        if end_date:
            query = query.where(Candle.timestamp <= end_date)

        # Order by timestamp descending (newest first)
        query = query.order_by(desc(Candle.timestamp))

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        candles = result.scalars().all()

        # Convert to response schema
        return [
            CandleResponse(
                listing_id=candle.listing_id,
                timestamp=candle.timestamp,
                interval=candle.interval,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                trades_count=candle.trades_count,
                created_at=candle.created_at,
            )
            for candle in candles
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying candles: {str(e)}"
        )


@router.get("/candles/latest", response_model=List[CandleResponse])
async def get_latest_candles(
    interval: str = Query("1m", description="Candle interval"),
    limit: int = Query(10, ge=1, le=100, description="Number of candles per listing"),
    db: AsyncSession = Depends(get_db),
) -> List[CandleResponse]:
    """
    Get latest candles for all active listings.

    **Query Parameters:**
    - `interval`: Candle interval (default: 1m)
    - `limit`: Candles per listing (default: 10, max: 100)

    **Returns:**
    - Latest candles for each active listing

    **Example:**
    ```
    GET /api/v1/candles/latest?interval=1m&limit=10
    ```
    """
    try:
        # Query to get latest candles for each listing
        # Using a window function would be more efficient, but for simplicity:
        query = text("""
            SELECT DISTINCT ON (listing_id)
                listing_id,
                timestamp,
                interval,
                open,
                high,
                low,
                close,
                volume,
                trades_count,
                created_at
            FROM candle
            WHERE interval = :interval
            ORDER BY listing_id, timestamp DESC
            LIMIT :limit
        """)

        result = await db.execute(
            query,
            {"interval": interval, "limit": limit}
        )

        candles = []
        for row in result:
            candles.append(
                CandleResponse(
                    listing_id=row[0],
                    timestamp=row[1],
                    interval=row[2],
                    open=row[3],
                    high=row[4],
                    low=row[5],
                    close=row[6],
                    volume=row[7],
                    trades_count=row[8],
                    created_at=row[9],
                )
            )

        return candles

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest candles: {str(e)}"
        )


@router.get("/candles/{listing_id}/latest", response_model=CandleResponse)
async def get_latest_candle_for_listing(
    listing_id: int,
    interval: str = Query("1m", description="Candle interval"),
    db: AsyncSession = Depends(get_db),
) -> CandleResponse:
    """
    Get the latest candle for a specific listing.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Query Parameters:**
    - `interval`: Candle interval (default: 1m)

    **Returns:**
    - Most recent candle

    **Example:**
    ```
    GET /api/v1/candles/1/latest?interval=1m
    ```
    """
    try:
        query = (
            select(Candle)
            .where(
                Candle.listing_id == listing_id,
                Candle.interval == interval
            )
            .order_by(desc(Candle.timestamp))
            .limit(1)
        )

        result = await db.execute(query)
        candle = result.scalar_one_or_none()

        if not candle:
            raise HTTPException(
                status_code=404,
                detail=f"No candles found for listing {listing_id} with interval {interval}"
            )

        return CandleResponse(
            listing_id=candle.listing_id,
            timestamp=candle.timestamp,
            interval=candle.interval,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            trades_count=candle.trades_count,
            created_at=candle.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest candle: {str(e)}"
        )
