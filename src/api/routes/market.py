"""
Market snapshot and aggregated data endpoints.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db

router = APIRouter()


@router.get("/market/snapshot")
async def get_market_snapshot(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get latest market data snapshot for all active listings.

    Combines latest candle, funding rate, and open interest for each listing.

    **Returns:**
    - List of market snapshots with:
      - Listing information
      - Latest candle (1m interval)
      - Latest funding rate
      - Latest open interest

    **Example:**
    ```
    GET /api/v1/market/snapshot
    ```
    """
    try:
        query = text("""
            WITH latest_candle AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as candle_timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM candle
                WHERE interval = '1m'
                ORDER BY listing_id, timestamp DESC
            ),
            latest_funding AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as funding_timestamp,
                    rate as funding_rate,
                    mark_price,
                    next_funding_time
                FROM funding_rate
                ORDER BY listing_id, timestamp DESC
            ),
            latest_oi AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as oi_timestamp,
                    open_interest
                FROM open_interest
                ORDER BY listing_id, timestamp DESC
            )
            SELECT
                l.id as listing_id,
                l.ccxt_symbol,
                e.name as exchange_name,
                c.symbol as coin_symbol,
                lt.type as listing_type,
                l.is_active,
                lc.candle_timestamp,
                lc.open,
                lc.high,
                lc.low,
                lc.close,
                lc.volume,
                lf.funding_timestamp,
                lf.funding_rate,
                lf.mark_price,
                lf.next_funding_time,
                lo.oi_timestamp,
                lo.open_interest
            FROM listing l
            JOIN exchange e ON l.exchange_id = e.id
            JOIN coin c ON l.coin_id = c.id
            JOIN listing_type lt ON l.listing_type_id = lt.id
            LEFT JOIN latest_candle lc ON l.id = lc.listing_id
            LEFT JOIN latest_funding lf ON l.id = lf.listing_id
            LEFT JOIN latest_oi lo ON l.id = lo.listing_id
            WHERE l.is_active = true
            ORDER BY l.id
        """)

        result = await db.execute(query)

        snapshots = []
        for row in result:
            snapshot = {
                "listing": {
                    "id": row[0],
                    "ccxt_symbol": row[1],
                    "exchange_name": row[2],
                    "coin_symbol": row[3],
                    "listing_type": row[4],
                    "is_active": row[5],
                },
                "candle": {
                    "timestamp": row[6].isoformat() if row[6] else None,
                    "open": float(row[7]) if row[7] else None,
                    "high": float(row[8]) if row[8] else None,
                    "low": float(row[9]) if row[9] else None,
                    "close": float(row[10]) if row[10] else None,
                    "volume": float(row[11]) if row[11] else None,
                } if row[6] else None,
                "funding": {
                    "timestamp": row[12].isoformat() if row[12] else None,
                    "rate": float(row[13]) if row[13] else None,
                    "mark_price": float(row[14]) if row[14] else None,
                    "next_funding_time": row[15].isoformat() if row[15] else None,
                } if row[12] else None,
                "open_interest": {
                    "timestamp": row[16].isoformat() if row[16] else None,
                    "value": float(row[17]) if row[17] else None,
                } if row[16] else None,
                "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            snapshots.append(snapshot)

        return snapshots

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying market snapshot: {str(e)}"
        )


@router.get("/market/{listing_id}/snapshot")
async def get_listing_snapshot(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get latest market data snapshot for a specific listing.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Returns:**
    - Market snapshot for the listing

    **Example:**
    ```
    GET /api/v1/market/1/snapshot
    ```
    """
    try:
        query = text("""
            WITH latest_candle AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as candle_timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM candle
                WHERE interval = '1m' AND listing_id = :listing_id
                ORDER BY listing_id, timestamp DESC
            ),
            latest_funding AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as funding_timestamp,
                    rate as funding_rate,
                    mark_price,
                    next_funding_time
                FROM funding_rate
                WHERE listing_id = :listing_id
                ORDER BY listing_id, timestamp DESC
            ),
            latest_oi AS (
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    timestamp as oi_timestamp,
                    open_interest
                FROM open_interest
                WHERE listing_id = :listing_id
                ORDER BY listing_id, timestamp DESC
            )
            SELECT
                l.id as listing_id,
                l.ccxt_symbol,
                e.name as exchange_name,
                c.symbol as coin_symbol,
                lt.type as listing_type,
                l.is_active,
                lc.candle_timestamp,
                lc.open,
                lc.high,
                lc.low,
                lc.close,
                lc.volume,
                lf.funding_timestamp,
                lf.funding_rate,
                lf.mark_price,
                lf.next_funding_time,
                lo.oi_timestamp,
                lo.open_interest
            FROM listing l
            JOIN exchange e ON l.exchange_id = e.id
            JOIN coin c ON l.coin_id = c.id
            JOIN listing_type lt ON l.listing_type_id = lt.id
            LEFT JOIN latest_candle lc ON l.id = lc.listing_id
            LEFT JOIN latest_funding lf ON l.id = lf.listing_id
            LEFT JOIN latest_oi lo ON l.id = lo.listing_id
            WHERE l.id = :listing_id
        """)

        result = await db.execute(query, {"listing_id": listing_id})
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Listing {listing_id} not found"
            )

        snapshot = {
            "listing": {
                "id": row[0],
                "ccxt_symbol": row[1],
                "exchange_name": row[2],
                "coin_symbol": row[3],
                "listing_type": row[4],
                "is_active": row[5],
            },
            "candle": {
                "timestamp": row[6].isoformat() if row[6] else None,
                "open": float(row[7]) if row[7] else None,
                "high": float(row[8]) if row[8] else None,
                "low": float(row[9]) if row[9] else None,
                "close": float(row[10]) if row[10] else None,
                "volume": float(row[11]) if row[11] else None,
            } if row[6] else None,
            "funding": {
                "timestamp": row[12].isoformat() if row[12] else None,
                "rate": float(row[13]) if row[13] else None,
                "mark_price": float(row[14]) if row[14] else None,
                "next_funding_time": row[15].isoformat() if row[15] else None,
            } if row[12] else None,
            "open_interest": {
                "timestamp": row[16].isoformat() if row[16] else None,
                "value": float(row[17]) if row[17] else None,
            } if row[16] else None,
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return snapshot

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying listing snapshot: {str(e)}"
        )
