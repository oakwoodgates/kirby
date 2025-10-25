"""
Market snapshot and aggregated data endpoints.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.utils.interval_manager import IntervalManager

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


@router.get("/market/{listing_id}/intervals")
async def get_listing_interval_stats(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get interval statistics for a specific listing.

    Shows latest candle timestamp and record count for each configured interval.

    **Path Parameters:**
    - `listing_id`: Listing ID

    **Returns:**
    - Listing information
    - Configured intervals from collector_config
    - Statistics per interval (latest timestamp, total candles, polling frequency)

    **Example:**
    ```
    GET /api/v1/market/1/intervals
    ```

    **Response:**
    ```json
    {
      "listing": {
        "id": 1,
        "ccxt_symbol": "BTC/USDC:USDC",
        "exchange_name": "hyperliquid",
        "coin_symbol": "BTC"
      },
      "configured_intervals": ["1m", "15m", "4h", "1d"],
      "interval_stats": {
        "1m": {
          "latest_timestamp": "2025-01-15T10:30:00Z",
          "total_candles": 43200,
          "polling_frequency_seconds": 30,
          "display_name": "1 Minute"
        },
        "15m": {...},
        "4h": {...},
        "1d": {...}
      }
    }
    ```
    """
    try:
        # Get listing info including collector_config
        listing_query = text("""
            SELECT
                l.id,
                l.ccxt_symbol,
                l.collector_config,
                e.name as exchange_name,
                c.symbol as coin_symbol
            FROM listing l
            JOIN exchange e ON l.exchange_id = e.id
            JOIN coin c ON l.coin_id = c.id
            WHERE l.id = :listing_id
        """)

        result = await db.execute(listing_query, {"listing_id": listing_id})
        listing_row = result.first()

        if not listing_row:
            raise HTTPException(
                status_code=404,
                detail=f"Listing {listing_id} not found"
            )

        listing_id, ccxt_symbol, collector_config, exchange_name, coin_symbol = listing_row

        # Extract configured intervals from collector_config
        configured_intervals = []
        if collector_config:
            # Try new format first (candle_intervals array), fallback to old format
            configured_intervals = collector_config.get('candle_intervals') or [
                collector_config.get('candle_interval', '1m')
            ]

        # Validate intervals
        if configured_intervals:
            configured_intervals = IntervalManager.validate_intervals(configured_intervals)
        else:
            configured_intervals = ['1m']  # Default

        # Get statistics for each interval
        interval_stats = {}
        for interval in configured_intervals:
            # Query latest timestamp and count for this interval
            stats_query = text("""
                SELECT
                    MAX(timestamp) as latest_timestamp,
                    COUNT(*) as total_candles
                FROM candle
                WHERE listing_id = :listing_id
                  AND interval = :interval
            """)

            stats_result = await db.execute(
                stats_query,
                {"listing_id": listing_id, "interval": interval}
            )
            stats_row = stats_result.first()

            latest_timestamp, total_candles = stats_row if stats_row else (None, 0)

            # Get interval metadata from IntervalManager
            interval_info = IntervalManager.get_interval_info(interval)
            poll_freq = IntervalManager.get_poll_frequency(interval)

            interval_stats[interval] = {
                "latest_timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
                "total_candles": total_candles or 0,
                "polling_frequency_seconds": poll_freq,
                "display_name": interval_info["display_name"],
                "candles_per_day": interval_info["candles_per_day"],
                "interval_seconds": interval_info["seconds"],
            }

        return {
            "listing": {
                "id": listing_id,
                "ccxt_symbol": ccxt_symbol,
                "exchange_name": exchange_name,
                "coin_symbol": coin_symbol,
            },
            "configured_intervals": configured_intervals,
            "interval_stats": interval_stats,
            "query_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying interval statistics: {str(e)}"
        )


@router.get("/market/intervals/overview")
async def get_all_intervals_overview(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get overview of interval coverage across all active listings.

    Shows which intervals are configured and how many candles exist for each.

    **Returns:**
    - Summary of interval coverage per listing
    - Total candles per interval across all listings

    **Example:**
    ```
    GET /api/v1/market/intervals/overview
    ```

    **Response:**
    ```json
    {
      "listings": [
        {
          "listing_id": 1,
          "ccxt_symbol": "BTC/USDC:USDC",
          "configured_intervals": ["1m", "15m", "4h", "1d"],
          "interval_counts": {
            "1m": 43200,
            "15m": 2880,
            "4h": 180,
            "1d": 30
          }
        }
      ],
      "global_stats": {
        "total_listings": 2,
        "interval_totals": {
          "1m": 86400,
          "15m": 5760,
          "4h": 360,
          "1d": 60
        }
      }
    }
    ```
    """
    try:
        # Get all active listings with their configs
        listings_query = text("""
            SELECT
                l.id,
                l.ccxt_symbol,
                l.collector_config,
                e.name as exchange_name,
                c.symbol as coin_symbol
            FROM listing l
            JOIN exchange e ON l.exchange_id = e.id
            JOIN coin c ON l.coin_id = c.id
            WHERE l.is_active = true
            ORDER BY l.id
        """)

        result = await db.execute(listings_query)
        listings_data = []
        global_interval_totals = {}

        for row in result:
            listing_id, ccxt_symbol, collector_config, exchange_name, coin_symbol = row

            # Extract configured intervals
            configured_intervals = []
            if collector_config:
                configured_intervals = collector_config.get('candle_intervals') or [
                    collector_config.get('candle_interval', '1m')
                ]

            if configured_intervals:
                configured_intervals = IntervalManager.validate_intervals(configured_intervals)
            else:
                configured_intervals = ['1m']

            # Get counts for each interval
            interval_counts = {}
            for interval in configured_intervals:
                count_query = text("""
                    SELECT COUNT(*) as count
                    FROM candle
                    WHERE listing_id = :listing_id
                      AND interval = :interval
                """)

                count_result = await db.execute(
                    count_query,
                    {"listing_id": listing_id, "interval": interval}
                )
                count_row = count_result.first()
                count = count_row[0] if count_row else 0

                interval_counts[interval] = count

                # Add to global totals
                if interval not in global_interval_totals:
                    global_interval_totals[interval] = 0
                global_interval_totals[interval] += count

            listings_data.append({
                "listing_id": listing_id,
                "ccxt_symbol": ccxt_symbol,
                "exchange_name": exchange_name,
                "coin_symbol": coin_symbol,
                "configured_intervals": configured_intervals,
                "interval_counts": interval_counts,
            })

        return {
            "listings": listings_data,
            "global_stats": {
                "total_listings": len(listings_data),
                "interval_totals": global_interval_totals,
            },
            "query_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying intervals overview: {str(e)}"
        )
