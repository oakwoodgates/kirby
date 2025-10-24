"""
Open interest API endpoints.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.open_interest import OpenInterest
from src.schemas.open_interest import OpenInterestResponse

router = APIRouter()


@router.get("/open-interest", response_model=List[OpenInterestResponse])
async def get_open_interest(
    listing_id: int = Query(..., description="Listing ID to query"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601 format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[OpenInterestResponse]:
    """
    Query open interest with filters.

    **Query Parameters:**
    - `listing_id`: Listing ID (required)
    - `start_date`: Start timestamp (optional, ISO 8601)
    - `end_date`: End timestamp (optional, ISO 8601)
    - `limit`: Maximum results (default: 1000, max: 10000)
    - `offset`: Skip N records (default: 0)

    **Returns:**
    - List of open interest records ordered by timestamp (newest first)

    **Example:**
    ```
    GET /api/v1/open-interest?listing_id=1&limit=100
    ```
    """
    try:
        # Build query
        query = select(OpenInterest).where(OpenInterest.listing_id == listing_id)

        # Apply date filters
        if start_date:
            query = query.where(OpenInterest.timestamp >= start_date)
        if end_date:
            query = query.where(OpenInterest.timestamp <= end_date)

        # Order by timestamp descending (newest first)
        query = query.order_by(desc(OpenInterest.timestamp))

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        open_interest_records = result.scalars().all()

        # Convert to response schema
        return [
            OpenInterestResponse(
                listing_id=oi.listing_id,
                timestamp=oi.timestamp,
                open_interest=oi.open_interest,
                open_interest_value=oi.open_interest_value,
                created_at=oi.created_at,
            )
            for oi in open_interest_records
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying open interest: {str(e)}"
        )


@router.get("/open-interest/latest", response_model=List[OpenInterestResponse])
async def get_latest_open_interest(
    db: AsyncSession = Depends(get_db),
) -> List[OpenInterestResponse]:
    """
    Get latest open interest for all active listings.

    **Returns:**
    - Latest open interest for each active listing

    **Example:**
    ```
    GET /api/v1/open-interest/latest
    ```
    """
    try:
        # Get latest open interest for each listing
        query = text("""
            SELECT DISTINCT ON (listing_id)
                listing_id,
                timestamp,
                open_interest,
                open_interest_value,
                created_at
            FROM open_interest
            ORDER BY listing_id, timestamp DESC
        """)

        result = await db.execute(query)

        open_interest_records = []
        for row in result:
            open_interest_records.append(
                OpenInterestResponse(
                    listing_id=row[0],
                    timestamp=row[1],
                    open_interest=row[2],
                    open_interest_value=row[3],
                    created_at=row[4],
                )
            )

        return open_interest_records

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest open interest: {str(e)}"
        )


@router.get("/open-interest/{listing_id}/latest", response_model=OpenInterestResponse)
async def get_latest_open_interest_for_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
) -> OpenInterestResponse:
    """
    Get the latest open interest for a specific listing.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Returns:**
    - Most recent open interest

    **Example:**
    ```
    GET /api/v1/open-interest/1/latest
    ```
    """
    try:
        query = (
            select(OpenInterest)
            .where(OpenInterest.listing_id == listing_id)
            .order_by(desc(OpenInterest.timestamp))
            .limit(1)
        )

        result = await db.execute(query)
        open_interest = result.scalar_one_or_none()

        if not open_interest:
            raise HTTPException(
                status_code=404,
                detail=f"No open interest found for listing {listing_id}"
            )

        return OpenInterestResponse(
            listing_id=open_interest.listing_id,
            timestamp=open_interest.timestamp,
            open_interest=open_interest.open_interest,
            open_interest_value=open_interest.open_interest_value,
            created_at=open_interest.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying latest open interest: {str(e)}"
        )
