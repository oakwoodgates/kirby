"""
Listings API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_db
from src.models.listing import Listing
from src.schemas.listing import ListingResponse

router = APIRouter()


@router.get("/listings", response_model=List[ListingResponse])
async def get_listings(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
) -> List[ListingResponse]:
    """
    Get all listings.

    **Query Parameters:**
    - `active_only`: Return only active listings (default: true)

    **Returns:**
    - List of listings with exchange, coin, and type information

    **Example:**
    ```
    GET /api/v1/listings
    GET /api/v1/listings?active_only=false
    ```
    """
    try:
        # Build query with eager loading of relationships
        query = select(Listing).options(
            selectinload(Listing.exchange),
            selectinload(Listing.coin),
            selectinload(Listing.listing_type)
        )

        if active_only:
            query = query.where(Listing.is_active == True)

        # Execute query
        result = await db.execute(query)
        listings = result.scalars().all()

        # Convert to response schema
        return [
            ListingResponse(
                id=listing.id,
                exchange_id=listing.exchange_id,
                exchange_name=listing.exchange.name if listing.exchange else None,
                coin_id=listing.coin_id,
                coin_symbol=listing.coin.symbol if listing.coin else None,
                listing_type_id=listing.listing_type_id,
                listing_type_name=listing.listing_type.name if listing.listing_type else None,
                symbol=listing.symbol,
                exchange_symbol=listing.exchange_symbol,
                is_active=listing.is_active,
                collector_config=listing.collector_config,
                created_at=listing.created_at,
            )
            for listing in listings
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying listings: {str(e)}"
        )


@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """
    Get a specific listing by ID.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Returns:**
    - Listing details

    **Example:**
    ```
    GET /api/v1/listings/1
    ```
    """
    try:
        query = (
            select(Listing)
            .options(
                selectinload(Listing.exchange),
                selectinload(Listing.coin),
                selectinload(Listing.listing_type)
            )
            .where(Listing.id == listing_id)
        )

        result = await db.execute(query)
        listing = result.scalar_one_or_none()

        if not listing:
            raise HTTPException(
                status_code=404,
                detail=f"Listing {listing_id} not found"
            )

        return ListingResponse(
            id=listing.id,
            exchange_id=listing.exchange_id,
            exchange_name=listing.exchange.name if listing.exchange else None,
            coin_id=listing.coin_id,
            coin_symbol=listing.coin.symbol if listing.coin else None,
            listing_type_id=listing.listing_type_id,
            listing_type_name=listing.listing_type.name if listing.listing_type else None,
            symbol=listing.symbol,
            exchange_symbol=listing.exchange_symbol,
            is_active=listing.is_active,
            collector_config=listing.collector_config,
            created_at=listing.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying listing: {str(e)}"
        )
