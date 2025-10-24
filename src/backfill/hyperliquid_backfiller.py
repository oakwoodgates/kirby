"""
Hyperliquid backfiller for historical data ingestion using CCXT.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from src.backfill.base import BaseBackfiller


class HyperliquidBackfiller(BaseBackfiller):
    """
    Hyperliquid perpetual futures backfiller using CCXT REST API.

    Fetches historical data for:
    - Candles (OHLCV)
    - Funding rates
    - Open interest
    """

    def __init__(
        self,
        listing_id: int,
        symbol: str,
        start_date: datetime,
        end_date: datetime = None,
        **kwargs,
    ):
        """
        Initialize Hyperliquid backfiller.

        Args:
            listing_id: Database listing ID
            symbol: CCXT symbol format (e.g., 'BTC/USDC:USDC')
            start_date: Start date for historical data
            end_date: End date for historical data (defaults to now)
            **kwargs: Additional args passed to BaseBackfiller
        """
        super().__init__(
            exchange_name='hyperliquid',
            listing_id=listing_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )

    async def backfill_candles(self) -> int:
        """
        Backfill historical 1-minute candle data.

        Fetches candles in batches, respecting rate limits.

        Returns:
            Number of candles fetched and stored
        """
        total_candles = 0
        current_time = int(self.start_date.timestamp() * 1000)
        end_time = int(self.end_date.timestamp() * 1000)

        self.logger.info(
            f"Fetching candles from {self.start_date} to {self.end_date} "
            f"(batch_size={self.batch_size})"
        )

        while current_time < end_time:
            try:
                # Fetch batch of candles
                ohlcv_data = await self.fetch_ohlcv_batch(
                    since=current_time,
                    limit=self.batch_size,
                    timeframe='1m',
                )

                if not ohlcv_data:
                    self.logger.warning(f"No candles returned for timestamp {current_time}")
                    # Move forward by batch_size minutes if no data
                    current_time += self.batch_size * 60 * 1000
                    continue

                # Convert to database format
                candles = []
                for candle in ohlcv_data:
                    timestamp_ms, open_price, high, low, close, volume = candle
                    candles.append({
                        'listing_id': self.listing_id,
                        'timestamp': datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
                        'interval': '1m',
                        'open': Decimal(str(open_price)),
                        'high': Decimal(str(high)),
                        'low': Decimal(str(low)),
                        'close': Decimal(str(close)),
                        'volume': Decimal(str(volume)),
                        'trades_count': None,  # Not available from CCXT
                    })

                # Store in database
                if candles:
                    await self.writer.insert_candles_batch(candles)
                    total_candles += len(candles)
                    self.logger.info(
                        f"Stored {len(candles)} candles | "
                        f"Total: {total_candles} | "
                        f"Last: {candles[-1]['timestamp']}"
                    )

                    # Move to next batch (use last candle timestamp + 1 minute)
                    last_timestamp_ms = ohlcv_data[-1][0]
                    current_time = last_timestamp_ms + (60 * 1000)
                else:
                    # No candles in batch, move forward
                    current_time += self.batch_size * 60 * 1000

                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                self.logger.error(f"Error fetching candles at {current_time}: {e}", exc_info=True)
                # Move forward on error to avoid infinite loop
                current_time += self.batch_size * 60 * 1000
                await asyncio.sleep(1)  # Extra delay on error

        return total_candles

    async def backfill_funding_rates(self) -> int:
        """
        Backfill historical funding rate data.

        Hyperliquid funding rates are paid every 8 hours (00:00, 08:00, 16:00 UTC).

        Returns:
            Number of funding rate records fetched and stored
        """
        total_rates = 0
        current_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        self.logger.info(
            f"Fetching funding rates from {self.start_date} to {self.end_date}"
        )

        while current_date <= self.end_date:
            try:
                # Fetch funding rate history
                # Note: CCXT fetchFundingRateHistory returns rates for specific timestamps
                since = int(current_date.timestamp() * 1000)
                limit = 100  # Fetch ~100 records at a time (covers ~33 days at 8h intervals)

                funding_history = await self.exchange.fetch_funding_rate_history(
                    symbol=self.symbol,
                    since=since,
                    limit=limit,
                )

                if not funding_history:
                    self.logger.debug(f"No funding rates for {current_date}")
                    current_date += timedelta(days=30)  # Move forward a month
                    continue

                # Convert to database format
                rates = []
                for entry in funding_history:
                    # CCXT funding rate format:
                    # {
                    #     'info': {...},
                    #     'symbol': 'BTC/USDC:USDC',
                    #     'fundingRate': 0.0001,
                    #     'timestamp': 1234567890000,
                    #     'datetime': '2023-...',
                    # }
                    rates.append({
                        'listing_id': self.listing_id,
                        'timestamp': datetime.fromtimestamp(
                            entry['timestamp'] / 1000,
                            tz=timezone.utc
                        ),
                        'rate': Decimal(str(entry['fundingRate'])),
                        'predicted_rate': None,  # Not available from CCXT
                        'mark_price': None,  # Not in funding rate history
                        'index_price': None,
                        'premium': None,
                        'next_funding_time': None,
                    })

                # Store in database
                if rates:
                    await self.writer.insert_funding_rates_batch(rates)
                    total_rates += len(rates)
                    self.logger.info(
                        f"Stored {len(rates)} funding rates | "
                        f"Total: {total_rates} | "
                        f"Last: {rates[-1]['timestamp']}"
                    )

                    # Move to date after last fetched rate
                    last_timestamp = funding_history[-1]['timestamp']
                    current_date = datetime.fromtimestamp(
                        last_timestamp / 1000,
                        tz=timezone.utc
                    ) + timedelta(hours=8)
                else:
                    current_date += timedelta(days=30)

                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                self.logger.error(
                    f"Error fetching funding rates at {current_date}: {e}",
                    exc_info=True
                )
                current_date += timedelta(days=30)
                await asyncio.sleep(1)

        return total_rates

    async def backfill_open_interest(self) -> int:
        """
        Backfill historical open interest data.

        Note: CCXT does not provide historical OI data, only current OI.
        This method attempts to fetch current OI and stores it, but historical
        backfill is not supported by the exchange API.

        Returns:
            Number of open interest records fetched (typically 0 or 1 for current)
        """
        self.logger.warning(
            "Hyperliquid does not provide historical open interest via CCXT. "
            "Only current OI can be fetched. Real-time OI collection happens "
            "via WebSocket collector."
        )

        try:
            # Fetch current open interest
            oi_data = await self.exchange.fetch_open_interest(self.symbol)

            if oi_data and 'openInterest' in oi_data:
                oi_record = {
                    'listing_id': self.listing_id,
                    'timestamp': datetime.now(timezone.utc),
                    'open_interest': Decimal(str(oi_data['openInterest'])),
                    'open_interest_value': None,
                }

                await self.writer.insert_open_interest_batch([oi_record])
                self.logger.info(
                    f"Stored current open interest: {oi_record['open_interest']}"
                )
                return 1

        except Exception as e:
            self.logger.error(f"Error fetching open interest: {e}", exc_info=True)

        return 0
