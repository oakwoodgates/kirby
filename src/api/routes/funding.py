"""
Funding rates API endpoints.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.funding_rate import FundingRate
from src.schemas.funding_rate import FundingRateResponse

router = APIRouter()


@router.get("/funding-rates", response_model=List[FundingRateResponse])
async def get_funding_rates(
    listing_id: int = Query(..., description="Listing ID to query"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601 format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[FundingRateResponse]:
    """
    Query funding rates with filters.

    **Query Parameters:**
    - `listing_id`: Listing ID (required)
    - `start_date`: Start timestamp (optional, ISO 8601)
    - `end_date`: End timestamp (optional, ISO 8601)
    - `limit`: Maximum results (default: 1000, max: 10000)
    - `offset`: Skip N records (default: 0)

    **Returns:**
    - List of funding rates ordered by timestamp (newest first)

    **Example:**
    ```
    GET /api/v1/funding-rates?listing_id=1&limit=100
    ```
    """
    try:
        # Build query
        query = select(FundingRate).where(FundingRate.listing_id == listing_id)

        # Apply date filters
        if start_date:
            query = query.where(FundingRate.timestamp >= start_date)
        if end_date:
            query = query.where(FundingRate.timestamp <= end_date)

        # Order by timestamp descending (newest first)
        query = query.order_by(desc(FundingRate.timestamp))

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        funding_rates = result.scalars().all()

        # Convert to response schema
        return [
            FundingRateResponse(
                listing_id=fr.listing_id,
                timestamp=fr.timestamp,
                rate=fr.rate,
                predicted_rate=fr.predicted_rate,
                mark_price=fr.mark_price,
                index_price=fr.index_price,
                premium=fr.premium,
                next_funding_time=fr.next_funding_time,
                created_at=fr.created_at,
            )
            for fr in funding_rates
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying funding rates: {str(e)}"
        )


@router.get("/funding-rates/latest", response_model=List[FundingRateResponse])
async def get_latest_funding_rates(
    db: AsyncSession = Depends(get_db),
) -> List[FundingRateResponse]:
    """
    Get latest funding rates for all active listings.

    **Returns:**
    - Latest funding rate for each active listing

    **Example:**
    ```
    GET /api/v1/funding-rates/latest
    ```
    """
    try:
        # Get latest funding rate for each listing
        from sqlalchemy import text

        query = text("""
            SELECT DISTINCT ON (listing_id)
                listing_id,
                timestamp,
                rate,
                predicted_rate,
                mark_price,
                index_price,
                premium,
                next_funding_time,
                created_at
            FROM funding_rate
            ORDER BY listing_id, timestamp DESC
        """)

        result = await db.execute(query)

        funding_rates = []
        for row in result:
            funding_rates.append(
                FundingRateResponse(
                    listing_id=row[0],
                    timestamp=row[1],
                    rate=row[2],
                    predicted_rate=row[3],
                    mark_price=row[4],
                    index_price=row[5],
                    premium=row[6],
                    next_funding_time=row[7],
                    created_at=row[8],
                )
            )

        return funding_rates

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest funding rates: {str(e)}"
        )


@router.get("/funding-rates/{listing_id}/latest", response_model=FundingRateResponse)
async def get_latest_funding_rate_for_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
) -> FundingRateResponse:
    """
    Get the latest funding rate for a specific listing.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Returns:**
    - Most recent funding rate

    **Example:**
    ```
    GET /api/v1/funding-rates/1/latest
    ```
    """
    try:
        query = (
            select(FundingRate)
            .where(FundingRate.listing_id == listing_id)
            .order_by(desc(FundingRate.timestamp))
            .limit(1)
        )

        result = await db.execute(query)
        funding_rate = result.scalar_one_or_none()

        if not funding_rate:
            raise HTTPException(
                status_code=404,
                detail=f"No funding rates found for listing {listing_id}"
            )

        return FundingRateResponse(
            listing_id=funding_rate.listing_id,
            timestamp=funding_rate.timestamp,
            rate=funding_rate.rate,
            predicted_rate=funding_rate.predicted_rate,
            mark_price=funding_rate.mark_price,
            index_price=funding_rate.index_price,
            premium=funding_rate.premium,
            next_funding_time=funding_rate.next_funding_time,
            created_at=funding_rate.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest funding rate: {str(e)}"
        )
