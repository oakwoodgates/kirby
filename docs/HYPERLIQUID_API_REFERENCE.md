# Hyperliquid API Reference

> Comprehensive guide to all available data from Hyperliquid's API
> Research conducted: October 26, 2025
> For: Kirby Platform - Data Expansion Planning

---

## Table of Contents

- [Overview](#overview)
- [Data Sources Comparison](#data-sources-comparison)
- [Available Data Types](#available-data-types)
- [WebSocket Channels](#websocket-channels)
- [REST API Endpoints](#rest-api-endpoints)
- [CCXT Integration](#ccxt-integration)
- [Tested Examples](#tested-examples)
- [Recommendations for Kirby](#recommendations-for-kirby)
- [Proposed Database Schemas](#proposed-database-schemas)
- [Implementation Priority](#implementation-priority)
- [References](#references)

---

## Overview

Hyperliquid provides three main ways to access market data:

1. **Hyperliquid Python SDK** - Native WebSocket + REST API
2. **CCXT Library** - Standardized exchange interface
3. **Direct API Calls** - Raw HTTP/WebSocket connections

**Currently Using in Kirby**: Hyperliquid SDK WebSocket for candles

---

## Data Sources Comparison

| Feature | Hyperliquid SDK | CCXT | Direct API |
|---------|----------------|------|------------|
| **Real-time Data** | ✅ WebSocket | ❌ Polling only | ✅ WebSocket |
| **Funding Rates** | ✅ WebSocket + REST | ✅ REST only | ✅ Both |
| **Open Interest** | ✅ WebSocket + REST | ✅ REST only | ✅ Both |
| **Order Book** | ✅ WebSocket + REST | ✅ REST only | ✅ Both |
| **Candles** | ✅ WebSocket + REST | ✅ REST only | ✅ Both |
| **Trades** | ✅ WebSocket + REST | ✅ REST only | ✅ Both |
| **Ease of Use** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Performance** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Multi-Exchange** | ❌ Hyperliquid only | ✅ 100+ exchanges | ❌ Single |

**Recommendation**:
- **Real-time collection**: Hyperliquid SDK (WebSocket)
- **Historical backfill**: CCXT (standardized interface)
- **Future multi-exchange**: Build abstraction layer using both

---

## Available Data Types

### ✅ Currently Collecting

1. **OHLCV Candles**
   - Source: Hyperliquid SDK WebSocket
   - Frequency: Real-time updates
   - Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M
   - Storage: TimescaleDB `candles` table
   - Status: ✅ **Production**

2. **Funding Rates**
   - Source: Hyperliquid SDK WebSocket (`activeAssetCtx` channel)
   - Frequency: Real-time updates with 1-minute buffering
   - Storage: TimescaleDB `funding_rates` table
   - Storage Strategy: 98.3% reduction (1-minute intervals vs per-second)
   - Historical Backfill: Available via `fundingHistory` (⚠️ limited fields: rate + premium only)
   - Status: ✅ **Production**

3. **Open Interest**
   - Source: Hyperliquid SDK WebSocket (`activeAssetCtx` channel)
   - Frequency: Real-time updates with 1-minute buffering
   - Storage: TimescaleDB `open_interest` table
   - Storage Strategy: 1-minute intervals aligned with candles
   - Historical Backfill: ❌ Not available from Hyperliquid API
   - Status: ✅ **Production**

### 📊 HIGH PRIORITY - Recommended Next

4. **Order Book (L2 Depth)**
   - **What**: Best bid/ask levels with sizes
   - **Why**: Liquidity analysis, support/resistance
   - **Available from**:
     - WebSocket: `l2Book` channel (up to 20 levels per side)
     - REST: `l2Book` endpoint (snapshot)
     - CCXT: `fetch_order_book(limit=20)`
   - **Data Fields**:
     - `bids`: Array of [price, size, num_orders]
     - `asks`: Array of [price, size, num_orders]
     - `timestamp`: Snapshot time
   - **Collection Frequency**: Real-time (throttle to every 1-5 seconds)
   - **Use Cases**:
     - Depth analysis
     - Slippage estimation
     - Whale watching (large orders)
     - Support/resistance levels

### 📈 MEDIUM PRIORITY

5. **Recent Trades**
   - **What**: Individual market trades (price, size, side)
   - **Why**: Market flow, volume profile analysis
   - **Available from**:
     - WebSocket: `trades` channel
     - REST: Recent trades endpoint
     - CCXT: `fetch_trades()`
   - **Data Fields**:
     - `price`: Trade price
     - `size`: Trade size
     - `side`: Buy or sell
     - `timestamp`: When trade executed
   - **Collection Frequency**: Real-time stream
   - **Use Cases**:
     - Aggressive buyer/seller identification
     - Volume profile construction
     - Time & sales analysis

6. **Ticker Data (24h Stats)**
   - **What**: 24-hour market statistics
   - **Why**: Quick market overview
   - **Available from**:
     - REST: `allMids` for all assets
     - CCXT: `fetch_ticker()` or `fetch_tickers()`
   - **Data Fields**:
     - `last`: Last price
     - `bid`, `ask`: Best bid/ask
     - `high`, `low`: 24h range
     - `volume`: 24h volume
     - `change`, `percentage`: 24h change
   - **Collection Frequency**: Every 1-5 minutes
   - **Use Cases**:
     - Market screening
     - Volatility analysis
     - Quick comparisons

7. **All Mids (Price Feed)**
   - **What**: Current mid price for all assets
   - **Why**: Fast price updates for all markets
   - **Available from**:
     - WebSocket: `allMids` channel (single subscription, all prices)
     - REST: `allMids` endpoint
   - **Data Fields**: Dict of `{coin: mid_price}`
   - **Collection Frequency**: Real-time updates
   - **Use Cases**:
     - Portfolio valuation
     - Correlation analysis
     - Market scanning

### 💡 NICE TO HAVE

8. **Liquidations**
   - **What**: Forced position closures
   - **Why**: Volatility indicator, cascading liquidation detection
   - **Available from**:
     - WebSocket: `userEvents` channel
     - REST: Historical queries (requires user context)
   - **Note**: May require per-user tracking or aggregate data
   - **Use Cases**:
     - Volatility spikes
     - Cascade detection
     - Risk management

9. **BBO (Best Bid/Offer)**
   - **What**: Top of book only (faster than full L2)
   - **Why**: Lightweight spread tracking
   - **Available from**:
     - WebSocket: `bbo` channel
   - **Data Fields**: Best bid price/size, best ask price/size
   - **Use Cases**:
     - Spread monitoring
     - Tick data for HFT analysis

10. **User-Specific Data** (Future - requires authentication)
    - Position updates
    - Order updates
    - Fill notifications
    - Funding payments
    - Account balances

---

## WebSocket Channels

### Base URL
```
wss://api.hyperliquid.xyz/ws
```

### Subscription Format
```json
{
  "method": "subscribe",
  "subscription": {
    "type": "<channel_type>",
    ...params
  }
}
```

### Available Channels

| Channel | Subscription | Data Type | Use in Kirby |
|---------|-------------|-----------|--------------|
| `candle` | `{"type":"candle","coin":"BTC","interval":"1m"}` | OHLCV candles | ✅ **Active** |
| `l2Book` | `{"type":"l2Book","coin":"BTC"}` | Order book (20 levels) | 🎯 High Priority |
| `trades` | `{"type":"trades","coin":"BTC"}` | Trade stream | 📊 Medium Priority |
| `allMids` | `{"type":"allMids","dex":""}` | All asset prices | 📊 Medium Priority |
| `activeAssetCtx` | `{"type":"activeAssetCtx","coin":"BTC"}` | **Funding, OI, mark price** | 🎯 **High Priority** |
| `bbo` | `{"type":"bbo","coin":"BTC"}` | Best bid/offer only | 💡 Nice to have |
| `notification` | `{"type":"notification","user":"0x..."}` | User notifications | 🔐 Future (auth) |
| `orderUpdates` | `{"type":"orderUpdates","user":"0x..."}` | Order status | 🔐 Future (auth) |
| `userFills` | `{"type":"userFills","user":"0x..."}` | Fill notifications | 🔐 Future (auth) |
| `userFundings` | `{"type":"userFundings","user":"0x..."}` | Funding payments | 🔐 Future (auth) |

**Note**: User-specific channels require wallet address and may need authentication for private data.

---

## REST API Endpoints

### Base URL
```
POST https://api.hyperliquid.xyz/info
```

All endpoints use POST with JSON body specifying `type` and parameters.

### Market Data Endpoints

#### 1. All Mids (Current Prices)
```json
POST /info
{
  "type": "allMids",
  "dex": ""
}
```
**Response**: `{"APE": "4.33245", "ARB": "1.21695", ...}`

#### 2. Meta and Asset Contexts (Funding, OI, Prices)
```json
POST /info
{
  "type": "metaAndAssetCtxs"
}
```
**Returns**:
- `meta`: Universe of tradeable assets
- `assetCtxs`: Array of contexts with:
  - `dayNtlVlm`: 24h notional volume
  - `funding`: Current funding rate
  - `openInterest`: Total OI
  - `oraclePx`: Oracle price
  - `markPx`: Mark price
  - `premium`: Perpetual premium
  - `prevDayPx`: Previous day's price

#### 3. L2 Order Book Snapshot
```json
POST /info
{
  "type": "l2Book",
  "coin": "BTC",
  "nSigFigs": null,
  "mantissa": null
}
```
**Returns**: Up to 20 levels per side with price, size, and order count.

#### 4. Candle Snapshot
```json
POST /info
{
  "type": "candleSnapshot",
  "req": {
    "coin": "BTC",
    "interval": "15m",
    "startTime": 1234567890000,
    "endTime": 1234567890000
  }
}
```
**Intervals**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M
**Limit**: Maximum 500 candles per request (pagination required)

#### 5. Funding History
```json
POST /info
{
  "type": "fundingHistory",
  "coin": "BTC",
  "startTime": 1234567890000,
  "endTime": 1234567890000  // optional
}
```
**Returns**: Historical funding rates with timestamps and premiums.

#### 6. Predicted Fundings
```json
POST /info
{
  "type": "predictedFundings"
}
```
**Returns**: Funding predictions across venues (Binance, Bybit, Hyperliquid).

#### 7. User State (requires user address)
```json
POST /info
{
  "type": "clearinghouseState",
  "user": "0x..."
}
```
**Returns**: Positions, margin, leverage, withdrawable balance.

---

## CCXT Integration

### Verified Working Methods

```python
import ccxt

exchange = ccxt.hyperliquid()
exchange.load_markets()

# 1. Ticker (includes funding, OI, mark/index prices)
ticker = exchange.fetch_ticker('BTC/USDC:USDC')
# Returns: last, bid, ask, mark_price, funding_rate, open_interest, etc.

# 2. Funding Rate
funding = exchange.fetch_funding_rate('BTC/USDC:USDC')
# Returns: fundingRate, fundingTimestamp, markPrice, indexPrice

# 3. Funding Rate History
history = exchange.fetch_funding_rate_history('BTC/USDC:USDC', limit=100)
# Returns: Array of historical funding rates

# 4. Order Book
book = exchange.fetch_order_book('BTC/USDC:USDC', limit=20)
# Returns: {bids: [[price, amount], ...], asks: [[price, amount], ...]}

# 5. Recent Trades
trades = exchange.fetch_trades('BTC/USDC:USDC', limit=100)
# Returns: Array of trades with price, amount, side, timestamp

# 6. OHLCV Candles
candles = exchange.fetch_ohlcv('BTC/USDC:USDC', '1m', limit=100)
# Returns: [[timestamp, open, high, low, close, volume], ...]

# 7. Open Interest
oi = exchange.fetch_open_interest('BTC/USDC:USDC')
# Returns: Open interest data

# 8. Open Interest History
oi_history = exchange.fetch_open_interest_history('BTC/USDC:USDC', '1h', limit=100)
# Returns: Historical OI data
```

**Important**: CCXT uses `USDC` as quote currency, our DB uses `USD`. Need mapping layer.

---

## Tested Examples

### CCXT Ticker Response
```json
{
  "symbol": "BTC/USDC:USDC",
  "timestamp": null,
  "datetime": null,
  "previousClose": 111486.0,
  "close": 115151.5,
  "bid": 115151.0,
  "ask": 115152.0,
  "quoteVolume": 2943869032.90,
  "info": {
    "name": "BTC",
    "maxLeverage": "40",
    "funding": "0.0000241762",       // ← Funding rate
    "openInterest": "30311.36624",   // ← Open interest
    "prevDayPx": "111486.0",
    "dayNtlVlm": "2943869032.90",
    "premium": "0.0007908917",       // ← Premium to index
    "oraclePx": "115060.0",          // ← Oracle price
    "markPx": "115140.0",            // ← Mark price
    "midPx": "115151.5",
    "dayBaseVlm": "25920.57095"
  }
}
```

### CCXT Funding Rate Response
```json
{
  "symbol": "BTC/USDC:USDC",
  "markPrice": 115158.0,
  "indexPrice": 115077.0,
  "fundingRate": 0.0000242817,
  "fundingTimestamp": 1761537600000,
  "fundingDatetime": "2025-10-27T04:00:00.000Z",
  "interval": "1h"
}
```

### CCXT Order Book Response
```json
{
  "bids": [
    [115141.0, 4.05124],
    [115140.0, 0.88136],
    [115139.0, 1.09662]
  ],
  "asks": [
    [115142.0, 2.04114],
    [115143.0, 0.30394],
    [115144.0, 0.04342]
  ],
  "timestamp": 1761533721000,
  "datetime": "2025-10-27T02:55:21.000Z"
}
```

---

## Recommendations for Kirby

### Phase 1: Funding Rates (START HERE)

**Why First**:
- Most requested feature for perps traders
- Relatively simple to implement
- High value-to-effort ratio

**Implementation**:
1. Create `FundingRateCollector` class
2. Subscribe to WebSocket `activeAssetCtx` channel
3. Store funding snapshots every hour (or on change)
4. Add REST endpoint: `GET /funding-rates/{exchange}/{coin}/{quote}`
5. Backfill historical data using CCXT

**Database**: See schema below

### Phase 2: Open Interest

**Why Second**:
- Available in same WebSocket channel as funding
- Minimal extra effort after Phase 1
- Complements funding rate data

**Implementation**:
1. Extend `FundingRateCollector` to also capture OI
2. Store OI snapshots at intervals
3. Add REST endpoint: `GET /open-interest/{exchange}/{coin}/{quote}`

**Database**: See schema below

### Phase 3: Order Book Snapshots (OPTIONAL)

**Why Third**:
- More complex (larger data volume)
- Requires careful throttling
- Not critical for all use cases

**Implementation**:
1. Create `OrderBookCollector` class
2. Subscribe to `l2Book` WebSocket channel
3. Store periodic snapshots (e.g., every 5 min or on 10% change)
4. Add REST endpoint: `GET /order-book/{exchange}/{coin}/{quote}`

**Consider**: Snapshot frequency vs storage costs

---

## Proposed Database Schemas

### funding_rates Table

```sql
CREATE TABLE funding_rates (
    id SERIAL PRIMARY KEY,
    starlisting_id INTEGER NOT NULL REFERENCES starlistings(id),
    time TIMESTAMPTZ NOT NULL,

    -- Core funding data
    funding_rate DECIMAL(20, 10) NOT NULL,  -- Current funding rate
    premium DECIMAL(20, 10),                -- Premium to index

    -- Price context
    mark_price DECIMAL(20, 4),              -- Perpetual mark price
    index_price DECIMAL(20, 4),             -- Spot index price
    oracle_price DECIMAL(20, 4),            -- Oracle price
    mid_price DECIMAL(20, 4),               -- Mid price

    -- Timing
    next_funding_time TIMESTAMPTZ,          -- When next funding applies

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure uniqueness per time period
    UNIQUE(starlisting_id, time)
);

-- Create hypertable for time-series optimization
SELECT create_hypertable('funding_rates', 'time');

-- Indexes for common queries
CREATE INDEX idx_funding_rates_starlisting_time ON funding_rates(starlisting_id, time DESC);
CREATE INDEX idx_funding_rates_time ON funding_rates(time DESC);
```

**Estimated Size**: ~50 bytes per row × 24 snapshots/day × 8 starlistings = ~9.6 KB/day = ~3.5 MB/year

### open_interest Table

```sql
CREATE TABLE open_interest (
    id SERIAL PRIMARY KEY,
    starlisting_id INTEGER NOT NULL REFERENCES starlistings(id),
    time TIMESTAMPTZ NOT NULL,

    -- Open interest data
    open_interest DECIMAL(20, 8) NOT NULL,  -- Total position size in base currency
    notional_value DECIMAL(20, 4),          -- USD value of all positions

    -- Volume context
    day_base_volume DECIMAL(20, 8),         -- 24h base currency volume
    day_notional_volume DECIMAL(20, 4),     -- 24h USD volume

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(starlisting_id, time)
);

-- Create hypertable
SELECT create_hypertable('open_interest', 'time');

-- Indexes
CREATE INDEX idx_open_interest_starlisting_time ON open_interest(starlisting_id, time DESC);
CREATE INDEX idx_open_interest_time ON open_interest(time DESC);
```

**Estimated Size**: ~60 bytes per row × 288 snapshots/day (every 5 min) × 8 starlistings = ~138 KB/day = ~50 MB/year

### order_book_snapshots Table (OPTIONAL)

```sql
CREATE TABLE order_book_snapshots (
    id SERIAL PRIMARY KEY,
    starlisting_id INTEGER NOT NULL REFERENCES starlistings(id),
    time TIMESTAMPTZ NOT NULL,

    -- Order book levels (JSONB for flexibility)
    bids JSONB NOT NULL,  -- Array of [price, size, num_orders]
    asks JSONB NOT NULL,  -- Array of [price, size, num_orders]

    -- Derived metrics
    mid_price DECIMAL(20, 4),     -- (best_bid + best_ask) / 2
    spread DECIMAL(20, 4),         -- best_ask - best_bid
    spread_bps DECIMAL(10, 2),     -- Spread in basis points

    -- Depth metrics
    bid_depth_10 DECIMAL(20, 4),   -- Total bid size in top 10 levels
    ask_depth_10 DECIMAL(20, 4),   -- Total ask size in top 10 levels

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create hypertable
SELECT create_hypertable('order_book_snapshots', 'time');

-- Indexes
CREATE INDEX idx_orderbook_starlisting_time ON order_book_snapshots(starlisting_id, time DESC);
CREATE INDEX idx_orderbook_time ON order_book_snapshots(time DESC);

-- Optional: GIN index for JSONB queries
CREATE INDEX idx_orderbook_bids ON order_book_snapshots USING gin(bids);
CREATE INDEX idx_orderbook_asks ON order_book_snapshots USING gin(asks);
```

**Estimated Size**: ~2 KB per row (20 levels × 2 sides) × 288 snapshots/day × 8 starlistings = ~4.6 MB/day = ~1.7 GB/year

**Note**: Order book data is large! Consider:
- Storing only top 5-10 levels instead of 20
- Reducing snapshot frequency (e.g., every 15 min vs 5 min)
- Adding retention policies (e.g., keep 90 days)

---

## Implementation Priority

### ✅ Completed
1. ✅ **OHLCV Candles** - Production
2. ✅ **Funding Rates** - Production with 1-minute buffering
3. ✅ **Open Interest** - Production with 1-minute buffering

### Near-term (Phase 2)
4. **Ticker/Price Feeds** - Quick market stats
5. **Order Book Snapshots** - If liquidity analysis needed

### Future (Phase 3+)
6. **Recent Trades** - For flow analysis
7. **Liquidations** - Volatility indicators
8. **BBO** - Lightweight spread tracking
9. **User Data** - Requires authentication layer

---

## Rate Limits & Constraints

### WebSocket
- **Connection Limit**: Recommend 1-2 persistent connections
- **Subscriptions**: Can subscribe to multiple channels per connection
- **Throttling**: Automatic by exchange, no manual limits needed

### REST API
- **Rate Limit**: 1200 requests per minute (20/second)
- **Burst**: Short bursts allowed
- **Response Limits**:
  - Candles: Max 500 per request
  - Order book: Max 20 levels per side
  - Trades: Pagination required for large ranges

**Best Practice**: Prefer WebSocket for real-time, use REST for backfill/snapshots

---

## Storage Considerations

### Data Volume Estimates (per year, 8 starlistings)

| Data Type | Frequency | Size/Row | Daily | Yearly |
|-----------|-----------|----------|-------|--------|
| Candles (current) | 1m candles | 80 bytes | ~900 KB | ~328 MB |
| Funding Rates | **1 min** (buffered) | 50 bytes | ~576 KB | ~210 MB |
| Open Interest | **1 min** (buffered) | 60 bytes | ~691 KB | ~252 MB |
| Order Book | 5 min | 2 KB | ~4.6 MB | ~1.7 GB |
| Trades | Real-time | 100 bytes | Varies | ~1-5 GB |

**Total (current with Funding + OI)**: ~790 MB/year
**Total (with Order Book)**: ~2.3 GB/year

**Storage Optimization**: 1-minute buffering achieves 98.3% storage reduction vs per-second storage
**TimescaleDB Compression**: Expect 5-10x compression, reducing to ~80-160 MB/year for current data

---

## References

### Official Documentation
- **Hyperliquid Docs**: https://hyperliquid.gitbook.io/hyperliquid-docs/
- **WebSocket API**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket
- **WebSocket Subscriptions**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- **Info Endpoint**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- **Perpetuals API**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals

### Python Libraries
- **Hyperliquid Python SDK**: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- **CCXT**: https://github.com/ccxt/ccxt

### API Endpoints
- **WebSocket**: `wss://api.hyperliquid.xyz/ws`
- **REST**: `https://api.hyperliquid.xyz/info` (POST)

---

## Next Steps

1. **Review this document** and decide which data types to prioritize
2. **Answer key questions**:
   - Which data is most valuable for your use cases?
   - How frequently should we collect funding rates? (hourly? every change?)
   - Do you want order book depth? (high storage cost)
   - Need historical backfill for new data types?
3. **Design database migrations** for chosen data types
4. **Implement collectors** following the existing pattern
5. **Add API endpoints** to serve the new data
6. **Update documentation** with new endpoints

---

**Document Version**: 1.0
**Last Updated**: October 26, 2025
**Status**: Research Complete, Awaiting Implementation Decisions
