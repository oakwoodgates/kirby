# Kirby Architecture Documentation

## System Overview

Kirby is a high-performance cryptocurrency data ingestion platform designed to collect, store, and serve real-time and historical market data from multiple exchanges. The system prioritizes data accuracy, low latency, and horizontal scalability.

## Core Design Principles

1. **Hybrid Database Layer**: asyncpg for high-performance writes, SQLAlchemy for flexible reads
2. **Modular Collectors**: Exchange-agnostic design with specialized implementations
3. **Time-Series Optimization**: TimescaleDB hypertables with compression and retention policies
4. **Real-Time First**: WebSocket-based data collection with polling fallback
5. **Idempotent Operations**: All writes use UPSERT to handle duplicates gracefully
6. **Composable Listings**: Exchange + Coin + Type composition model

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXCHANGES                                 │
│  (Hyperliquid, Binance, Coinbase, etc.)                          │
└──────────────┬──────────────────────────────────────────────────┘
               │
               │ WebSocket / REST API
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA COLLECTORS                              │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  WebSocket       │  │  REST/Polling    │                     │
│  │  Collectors      │  │  Collectors      │                     │
│  │  (Real-time)     │  │  (Fallback)      │                     │
│  └────────┬─────────┘  └────────┬─────────┘                     │
│           │                     │                                │
│           └──────────┬──────────┘                                │
│                      │                                           │
│           ┌──────────▼─────────┐                                │
│           │  BaseCollector     │                                │
│           │  - CCXT Integration│                                │
│           │  - Reconnection    │                                │
│           │  - Heartbeats      │                                │
│           └──────────┬─────────┘                                │
└──────────────────────┼──────────────────────────────────────────┘
                       │
                       │ Normalized Data
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA WRITER                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  DataWriter (asyncpg)                                     │   │
│  │  - Batch inserts (1000+ records)                          │   │
│  │  - UPSERT (ON CONFLICT DO UPDATE)                         │   │
│  │  - Connection pooling (10-20 connections)                 │   │
│  └──────────────────────┬───────────────────────────────────┘   │
└─────────────────────────┼──────────────────────────────────────┘
                          │
                          │ Bulk Insert
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIMESCALEDB                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Hypertables (Time-Series)                                │   │
│  │  - candles (OHLCV)                                        │   │
│  │  - funding_rates                                          │   │
│  │  - open_interest                                          │   │
│  │  - trades                                                 │   │
│  │  - market_metadata                                        │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │  Relational Tables (Reference Data)                       │   │
│  │  - exchanges, coins, listing_types, listings              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Features: 7-day chunks, compression after 7 days, indexes       │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          │ SQLAlchemy Queries
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI REST API                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Routes                                                    │   │
│  │  - /api/v1/candles                                        │   │
│  │  - /api/v1/funding-rates                                  │   │
│  │  - /api/v1/open-interest                                  │   │
│  │  - /api/v1/listings                                       │   │
│  │  - /api/v1/market/snapshot                                │   │
│  │  - /api/v1/health                                         │   │
│  └──────────────────────┬───────────────────────────────────┘   │
└─────────────────────────┼──────────────────────────────────────┘
                          │
                          │ JSON/REST
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CLIENT APPLICATIONS                           │
│  (Trading Apps, Charting Tools, Analytics Platforms)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Data Collectors

**Purpose**: Ingest real-time and historical data from exchanges

**Key Classes**:
- `BaseCollector` - Abstract base with common functionality
- `HyperliquidWebSocketCollector` - Real-time WebSocket implementation
- `HyperliquidPollingCollector` - REST API fallback

**Responsibilities**:
1. Connect to exchange (WebSocket or REST)
2. Subscribe to data channels (candles, orderbook, funding, OI)
3. Normalize data to internal format
4. Write to database via DataWriter
5. Handle reconnections with exponential backoff
6. Send periodic heartbeats (30s intervals)

**Data Flow**:
```python
# WebSocket message received
exchange_message = {"type": "candle", "data": {...}}

# Normalize to internal format
candle = {
    "listing_id": 1,
    "timestamp": datetime(...),
    "interval": "1m",
    "open": Decimal("110000.00"),
    "high": Decimal("110500.00"),
    "low": Decimal("109800.00"),
    "close": Decimal("110200.00"),
    "volume": Decimal("125.5")
}

# Batch write to database
await writer.insert_candles_batch([candle])
```

**Thread Safety**:
- WebSocket callbacks run in separate thread
- Use `asyncio.run_coroutine_threadsafe()` to schedule async operations
- Store reference to main event loop

---

### 2. Backfill Service

**Purpose**: Fetch historical data for new listings or fill gaps

**Key Classes**:
- `BaseBackfiller` - Abstract base for backfill operations
- `HyperliquidBackfiller` - CCXT REST implementation

**Responsibilities**:
1. Query exchange REST API for historical data
2. Batch fetch (500-1000 records per request)
3. Rate limiting (configurable delays)
4. Progress tracking in `backfill_job` table
5. Resume from last checkpoint on failure

**Performance**:
- 270 candles/second typical throughput
- 4,320 candles (3 days) in ~16 seconds
- Configurable batch sizes and rate limits

**Job Tracking**:
```sql
CREATE TABLE backfill_job (
    id SERIAL PRIMARY KEY,
    listing_id INTEGER REFERENCES listing(id),
    data_type VARCHAR(50),  -- 'candles', 'funding_rates', 'open_interest'
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    status VARCHAR(20),  -- 'pending', 'running', 'completed', 'failed'
    records_fetched INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
```

---

### 3. Database Layer

#### 3.1 Write Path (asyncpg)

**Why asyncpg?**
- 3-5x faster than SQLAlchemy for bulk inserts
- Direct PostgreSQL wire protocol
- Low overhead, minimal abstractions

**DataWriter Class**:
```python
class DataWriter:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def insert_candles_batch(self, candles: List[Dict]) -> int:
        """Batch insert with UPSERT (ON CONFLICT DO UPDATE)"""
        async with self.pool.acquire() as conn:
            query = """
                INSERT INTO candle (listing_id, timestamp, interval, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (listing_id, timestamp, interval)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """
            await conn.executemany(query, candles)
```

**Connection Pool**:
- Min connections: 10
- Max connections: 20
- Timeout: 30 seconds
- Shared across all collectors

#### 3.2 Read Path (SQLAlchemy)

**Why SQLAlchemy?**
- Type-safe ORM with relationships
- Complex query building (filters, joins, aggregations)
- Automatic query optimization
- Easier to maintain than raw SQL

**Example Query**:
```python
from sqlalchemy import select
from src.models import Candle, Listing

# Query candles with joins
stmt = (
    select(Candle)
    .join(Listing)
    .where(
        Candle.listing_id == 1,
        Candle.timestamp >= start_date,
        Candle.timestamp <= end_date,
        Candle.interval == "1m"
    )
    .order_by(Candle.timestamp.desc())
    .limit(1000)
)

async with AsyncSession(engine) as session:
    result = await session.execute(stmt)
    candles = result.scalars().all()
```

---

### 4. TimescaleDB Schema

#### 4.1 Hypertables (Time-Series Data)

**Candles**:
```sql
CREATE TABLE candle (
    listing_id INTEGER NOT NULL REFERENCES listing(id),
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(10) NOT NULL,  -- '1m', '5m', '1h', etc.
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    trades_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (listing_id, timestamp, interval)
);

-- Convert to hypertable
SELECT create_hypertable('candle', 'timestamp', chunk_time_interval => INTERVAL '7 days');

-- Compression policy
ALTER TABLE candle SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'listing_id,interval'
);

SELECT add_compression_policy('candle', INTERVAL '7 days');
```

**Funding Rates**:
```sql
CREATE TABLE funding_rate (
    listing_id INTEGER NOT NULL REFERENCES listing(id),
    timestamp TIMESTAMPTZ NOT NULL,
    rate NUMERIC(20, 10) NOT NULL,
    predicted_rate NUMERIC(20, 10),
    mark_price NUMERIC(20, 8),
    index_price NUMERIC(20, 8),
    premium NUMERIC(20, 8),
    next_funding_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (listing_id, timestamp)
);

SELECT create_hypertable('funding_rate', 'timestamp', chunk_time_interval => INTERVAL '7 days');
```

**Open Interest**:
```sql
CREATE TABLE open_interest (
    listing_id INTEGER NOT NULL REFERENCES listing(id),
    timestamp TIMESTAMPTZ NOT NULL,
    open_interest NUMERIC(20, 8) NOT NULL,
    open_interest_value NUMERIC(20, 8),
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (listing_id, timestamp)
);

SELECT create_hypertable('open_interest', 'timestamp', chunk_time_interval => INTERVAL '7 days');
```

#### 4.2 Relational Tables (Reference Data)

**Exchanges**:
```sql
CREATE TABLE exchange (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    ccxt_id VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    api_config JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Listings** (Composable Model):
```sql
CREATE TABLE listing (
    id SERIAL PRIMARY KEY,
    exchange_id INTEGER REFERENCES exchange(id),
    coin_id INTEGER REFERENCES coin(id),
    listing_type_id INTEGER REFERENCES listing_type(id),
    symbol VARCHAR(50) NOT NULL,          -- CCXT symbol (BTC/USDC:USDC)
    exchange_symbol VARCHAR(50) NOT NULL, -- Native symbol (BTC-PERP)
    is_active BOOLEAN DEFAULT true,
    collector_config JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (exchange_id, symbol)
);
```

**Indexes**:
```sql
-- Performance indexes
CREATE INDEX idx_candle_listing_timestamp ON candle (listing_id, timestamp DESC);
CREATE INDEX idx_candle_listing_interval_timestamp ON candle (listing_id, interval, timestamp DESC);
CREATE INDEX idx_funding_listing_timestamp ON funding_rate (listing_id, timestamp DESC);
CREATE INDEX idx_oi_listing_timestamp ON open_interest (listing_id, timestamp DESC);
```

---

### 5. Configuration Management

**Pydantic Settings** ([src/config/settings.py](src/config/settings.py)):
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    ASYNCPG_URL: str
    DB_POOL_MIN_SIZE: int = 10
    DB_POOL_MAX_SIZE: int = 20

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4

    # Collectors
    COLLECTOR_HEARTBEAT_INTERVAL: int = 30
    COLLECTOR_RECONNECT_DELAY: int = 5
    COLLECTOR_MAX_RECONNECT_ATTEMPTS: int = 10

    # Backfill
    BACKFILL_BATCH_SIZE: int = 1000
    BACKFILL_RATE_LIMIT_DELAY: int = 1000

    class Config:
        env_file = ".env"

settings = Settings()
```

**Environment Variables** (.env):
```bash
DATABASE_URL=postgresql+asyncpg://kirby_user:kirby_pass@localhost:5432/kirby
ASYNCPG_URL=postgresql://kirby_user:kirby_pass@localhost:5432/kirby
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

### 6. Logging & Monitoring

**Structured Logging**:
```python
import logging
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Logs include context
logger.info(
    "Received candle",
    extra={
        "listing_id": 1,
        "exchange": "hyperliquid",
        "symbol": "BTC/USDC:USDC",
        "timestamp": "2025-10-24T10:00:00Z"
    }
)
```

**Output Formats**:
- **JSON**: Machine-readable for log aggregation
- **Text**: Human-readable for development

**Heartbeat Monitoring**:
- Collectors send heartbeat every 30s
- Logged with latest data timestamps
- Used for health checks

---

## Performance Characteristics

### Write Performance

| Metric | Value |
|--------|-------|
| Collector Write Latency | <10ms (asyncpg batch) |
| Candles/Second (Real-time) | 2 candles/min (BTC + HYPE) |
| Backfill Throughput | 270 candles/sec |
| Database Inserts/Sec | 50,000+ (asyncpg) |

### Read Performance (Expected)

| Metric | Value |
|--------|-------|
| Latest Candles Query | <50ms (indexed) |
| Range Query (1 day) | <200ms |
| Aggregation Query | <500ms (with compression) |
| Concurrent Requests | 100+ RPS (per worker) |

### Storage

| Data Type | Daily Volume (per listing) | Compressed Size |
|-----------|----------------------------|-----------------|
| 1m Candles | 1,440 records | ~50KB |
| Funding Rates | 3 records (8h intervals) | ~1KB |
| Open Interest | ~1,000 records | ~30KB |
| Total (2 listings) | ~162KB/day | ~82KB compressed |

**30-Day Estimate**: ~2.5MB compressed (BTC + HYPE)

---

## Scalability Considerations

### Horizontal Scaling

**Collectors**:
- One collector per listing
- Stateless (can restart anytime)
- Scale by adding more listings

**API**:
- Multiple Gunicorn workers
- Behind Nginx load balancer
- Stateless (session-less)

**Database**:
- TimescaleDB compression reduces storage 10-20x
- Can add read replicas for API queries
- Continuous aggregates for pre-computed metrics

### Vertical Scaling

**Current Requirements** (2 listings):
- 2GB RAM (database + collectors + API)
- 2 vCPU
- 10GB disk (30 days of data)

**Estimated for 100 listings**:
- 8GB RAM
- 4 vCPU
- 50GB disk (30 days, compressed)

---

## Error Handling & Resilience

### Collector Reconnection

```python
async def run_with_reconnection(self):
    while self.reconnect_count < self.max_reconnect_attempts:
        try:
            await self.run()
        except Exception as e:
            self.reconnect_count += 1
            delay = min(self.reconnect_delay * (2 ** self.reconnect_count), 300)
            logger.error(f"Collector error, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

### Idempotent Writes

All database writes use UPSERT:
```sql
INSERT INTO candle (...)
VALUES (...)
ON CONFLICT (listing_id, timestamp, interval)
DO UPDATE SET ...
```

This ensures:
- No duplicates from retries
- Safe concurrent writes
- Gap filling from backfill

### Graceful Shutdown

```python
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

async def handle_shutdown(sig):
    logger.info(f"Received {sig}, shutting down gracefully...")
    await collector.stop()
    await close_pool()
    sys.exit(0)
```

---

## Security Considerations

### Database Access
- Connection pool with credentials from environment
- No hardcoded secrets
- PostgreSQL SSL support (production)

### API Security (Phase 5)
- CORS configuration for allowed origins
- Rate limiting per client IP
- Optional API key authentication
- Input validation via Pydantic

### Docker
- Non-root user in containers
- Minimal base images
- Volume mounts for data persistence

---

## Future Enhancements

### Phase 7: WebSocket Streaming API
- Redis PubSub for real-time broadcasting
- Client subscriptions to specific listings/data types
- Backpressure handling

### Phase 8: Multi-Exchange Support
- Binance, Bybit, Coinbase collectors
- Exchange-specific quirks handled in subclasses
- Unified API regardless of source

### Phase 9: Advanced Features
- Continuous aggregates (1h/4h/1d pre-computed candles)
- Gap detection and automatic backfill triggers
- Data quality checks and anomaly detection
- Admin UI for listing management

---

## References

- [TimescaleDB Docs](https://docs.timescale.com/)
- [CCXT Documentation](https://docs.ccxt.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)