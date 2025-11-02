# Kirby Project Documentation

> **Project Name**: Kirby
> **Inspiration**: Nintendo character that inhales unlimited objects
> **Purpose**: Ingest real-time and historical market data from multiple exchanges, serve via REST API
> **Status**: ✅ **Production Ready** - All phases complete, deployed and collecting data

---

## Overview

Kirby is a high-performance market data ingestion and API system for cryptocurrency exchanges. It collects:
- **OHLCV candle data** in real-time via WebSocket
- **Funding rates** (1-minute intervals with buffering)
- **Open interest** (1-minute intervals with buffering)

All data is served via a FastAPI REST API to downstream applications (charting tools, AI/ML models, trading bots).

**Current Deployment**: Successfully deployed on Digital Ocean, collecting real-time candle, funding, and OI data from Hyperliquid exchange.

### Key Concept: Starlisting

A **starlisting** is a unique combination of:
- **Exchange** (e.g., Hyperliquid)
- **Trading Pair** = **Coin** (base asset) + **Quote Currency** (e.g., BTC/USD, SOL/USDC)
- **Market Type** (e.g., perps, spot, futures)
- **Interval** (e.g., 1m, 15m, 4h, 1d)

Example: `hyperliquid/BTC/USD/perps/15m` is one starlisting.

**Important**: A "coin" alone is not enough - BTC/USD ≠ BTC/USDC ≠ BTC/EUR. Each trading pair represents a distinct market with different prices and liquidity.

---

## Architecture

### Principles
1. **Secure**: Proper env var handling, data validation, input sanitization
2. **High Performance**: Async I/O, optimized bulk inserts via asyncpg, connection pooling, 1-minute buffering
3. **Modular & Composable**: Easy to add/remove exchanges, coins, intervals
4. **Production Ready**: Health checks, monitoring, structured logging, Docker deployment

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI + Uvicorn | High-performance async REST API |
| **Database** | TimescaleDB (PostgreSQL 16) | Time-series optimized storage with hypertables |
| **ORM (Reads)** | SQLAlchemy 2.0 async | Complex queries (API endpoints) |
| **DB Driver (Writes)** | asyncpg | High-performance bulk inserts (collectors) |
| **Validation** | Pydantic v2 | Type-safe schemas and settings |
| **Migrations** | Alembic (async) | Database schema versioning |
| **Exchange Integration** | Hyperliquid Python SDK + WebSockets | Real-time data collection |
| **Testing** | pytest + pytest-asyncio | 54 tests (26 unit, 28 integration) |
| **Deployment** | Docker + Docker Compose | Container orchestration |
| **Python Version** | 3.13 | Latest stable release |

### Data Flow

```
Real-time Collection (Candles):
Hyperliquid WebSocket → Collector → asyncpg (COPY/upsert) → TimescaleDB

Real-time Collection (Funding/OI):
Hyperliquid WebSocket → In-Memory Buffer → Flush every 60s → asyncpg → TimescaleDB

API Queries:
Client Apps → FastAPI → SQLAlchemy (read) → TimescaleDB → JSON Response

Configuration:
YAML (starlistings.yaml) → sync_config.py → Database tables
```

### Service Architecture

```
┌─────────────────────────────────────────────────────┐
│  Docker Compose Orchestration                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌────────────────┐  ┌──────────────────────────┐  │
│  │  TimescaleDB   │◄─┤  Candle Collector       │  │
│  │  (PostgreSQL)  │  │  (WebSocket client)      │  │
│  │  Port: 5432    │  │  Real-time OHLCV data    │  │
│  │                │  └──────────────────────────┘  │
│  │                │                                 │
│  │                │  ┌──────────────────────────┐  │
│  │                │◄─┤  Funding/OI Collector    │  │
│  │                │  │  (WebSocket client)      │  │
│  │                │  │  1-min buffering         │  │
│  └────────┬───────┘  └──────────────────────────┘  │
│           │                                         │
│           │          ┌──────────────────────────┐  │
│           └─────────►│  Kirby API               │  │
│                      │  (FastAPI/Uvicorn)       │  │
│                      │  Port: 8000              │  │
│                      └──────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Database Schema

### Reference Tables
- **exchanges**: Exchange definitions (id, name, display_name, active)
- **coins**: Base asset definitions (id, symbol, name, active) - e.g., BTC, ETH, SOL
- **quote_currencies**: Quote asset definitions (id, symbol, name, active) - e.g., USD, USDC, USDT
- **market_types**: Market type definitions (id, name, display_name, active) - e.g., perps, spot
- **intervals**: Time interval definitions (id, name, seconds, active) - e.g., 1m=60s, 15m=900s

### Core Tables

**starlistings**: Unique combinations of exchange + trading pair + market_type + interval
- Columns: id, exchange_id, coin_id, quote_currency_id, market_type_id, interval_id, active
- Unique constraint: `uq_starlisting` on all foreign keys
- Index: `ix_starlisting_lookup` for fast queries
- Helper method: `get_trading_pair()` returns "BTC/USD"
- Seed data: 8 starlistings (BTC/SOL × USD × perps × 1m/15m/4h/1d)

**candles**: TimescaleDB hypertable for OHLCV data
- Primary key: (time, starlisting_id) - composite for uniqueness
- Columns: open, high, low, close, volume (all Numeric), num_trades (Integer)
- Check constraints: OHLC consistency (high ≥ low, etc.), positive prices, non-negative volume
- Hypertable: Partitioned by time with 1-day chunks
- Indexes:
  - BRIN on time (efficient for time-series queries)
  - Composite on (starlisting_id, time) for fast filtering
- ON CONFLICT: Upsert support for reprocessing/backfill with COALESCE to preserve existing data

**funding_rates**: TimescaleDB hypertable for funding rate data (1-minute precision)
- Primary key: (time, starlisting_id) - composite for uniqueness
- Columns: funding_rate, premium, mark_price, index_price, oracle_price, mid_price, next_funding_time (all Numeric/Timestamptz)
- **Storage Strategy**: 1-minute intervals with buffering (1,440 records/day vs 86,400 at per-second)
- **Timestamp Format**: Minute-precision (seconds/microseconds truncated to 0)
- **Buffering**: In-memory buffer flushes every 60 seconds on minute boundary
- **Real-time Data**: Collector captures all price fields via WebSocket
- **Historical Data**: API only provides funding_rate + premium (no prices/OI)
- ON CONFLICT: Upsert with COALESCE to preserve existing data when backfill provides NULL

**open_interest**: TimescaleDB hypertable for OI data (1-minute precision)
- Primary key: (time, starlisting_id) - composite for uniqueness
- Columns: open_interest, notional_value, day_base_volume, day_notional_volume (all Numeric)
- **Storage Strategy**: 1-minute intervals with buffering (matches funding_rates)
- **Timestamp Format**: Minute-precision aligned with candles and funding
- **Real-time Only**: No historical OI data available from Hyperliquid API
- ON CONFLICT: Upsert with COALESCE to preserve existing data

### Timestamp Alignment

All tables use **minute-precision timestamps** aligned to the start of the minute for easy JOINs:
- Format: `2025-11-02 20:00:00+00` (seconds and microseconds are 0)
- Alignment function: `truncate_to_minute()` in `src/utils/helpers.py`
- Benefits: Easy to JOIN across tables on `time` column
- Example query: `SELECT * FROM candles c JOIN funding_rates f ON c.time = f.time AND c.starlisting_id = f.starlisting_id`

### Database Access Patterns

**Writes** (high-performance via asyncpg):
- Collectors use asyncpg pool directly
- Bulk upsert: `INSERT ... ON CONFLICT (time, starlisting_id) DO UPDATE`
- COALESCE pattern: `COALESCE(EXCLUDED.field, table.field)` preserves existing data
- ~10x faster than ORM for bulk inserts
- Connection pooling: 5-20 connections

**Reads** (complex queries via SQLAlchemy):
- API endpoints use SQLAlchemy async sessions
- Repository pattern for encapsulation
- **Critical**: Avoid lazy loading (causes greenlet errors)
- Use column selection or manual object construction

---

## Project Structure

```
kirby/
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── main.py            # App initialization, CORS, lifespan
│   │   ├── dependencies.py    # DB session dependency
│   │   └── routers/           # Route handlers
│   │       ├── candles.py     # Candle data endpoints
│   │       ├── funding.py     # Funding rate & open interest endpoints
│   │       ├── health.py      # Health check endpoints
│   │       └── starlistings.py # Starlisting endpoints
│   ├── collectors/             # Data collection services
│   │   ├── base.py            # BaseCollector abstract class
│   │   ├── hyperliquid.py     # Hyperliquid candle collector (WebSocket)
│   │   ├── hyperliquid_funding.py  # Hyperliquid funding/OI collector (1-min buffering)
│   │   └── main.py            # CollectorManager orchestrator
│   ├── db/                     # Database layer
│   │   ├── base.py            # SQLAlchemy Base, naming conventions
│   │   ├── models.py          # ORM models (Exchange, Coin, Starlisting, Candle, FundingRate, OpenInterest)
│   │   ├── connection.py      # asyncpg pool + SQLAlchemy engine
│   │   └── repositories.py    # Repository pattern (CRUD operations)
│   ├── schemas/                # Pydantic models
│   │   ├── candles.py         # CandleResponse, CandleListResponse
│   │   ├── health.py          # HealthResponse
│   │   └── starlistings.py    # StarlistingResponse, StarlistingListResponse
│   ├── config/                 # Configuration management
│   │   ├── settings.py        # Pydantic Settings (env vars)
│   │   └── loader.py          # YAML → database sync
│   └── utils/                  # Utilities
│       ├── helpers.py         # Timestamp conversion, validation, truncate_to_minute()
│       ├── logging.py         # Structured logging setup
│       └── export.py          # Export utilities (CSV/Parquet, metadata, time parsing)
├── tests/
│   ├── conftest.py            # Shared fixtures (test DB, client)
│   ├── unit/                  # Unit tests (26 tests)
│   │   └── test_helpers.py    # Helper function tests
│   └── integration/           # Integration tests (28 tests)
│       ├── test_api_*.py      # API endpoint tests
│       └── test_repositories.py # Repository tests
├── scripts/                    # Operational scripts
│   ├── sync_config.py         # Sync YAML config to database
│   ├── backfill.py            # Backfill historical candle data (CCXT)
│   ├── backfill_funding.py    # Backfill historical funding rates (Hyperliquid SDK)
│   ├── export_candles.py      # Export candle data to CSV/Parquet
│   ├── export_funding.py      # Export funding rate data to CSV/Parquet
│   ├── export_oi.py           # Export open interest data to CSV/Parquet
│   ├── export_all.py          # Export merged datasets for ML/backtesting
│   ├── test_collector_simple.py # Test real data collection
│   ├── test_full_system.py    # System verification
│   └── run_tests.py           # Test runner with DB setup
├── config/                     # Configuration files
│   └── starlistings.yaml      # Starlisting definitions
├── migrations/                 # Alembic migrations
│   ├── env.py                 # Async migration environment
│   └── versions/              # Migration files
│       ├── 20251026_0001_initial_schema.py  # Initial schema
│       └── 20251102_*_add_funding_oi.py     # Funding/OI tables
├── docs/                       # Documentation
│   ├── HYPERLIQUID_API_REFERENCE.md  # Hyperliquid API details
│   └── EXPORT.md              # Data export guide (ML/backtesting)
├── docker-compose.yml         # Service orchestration
├── Dockerfile                 # Production container image
├── .dockerignore              # Docker build optimization
├── deploy.sh                  # Automated deployment script
├── pyproject.toml             # Python dependencies
├── alembic.ini                # Alembic configuration
├── .env.example               # Environment variable template
├── README.md                  # User documentation
├── DEPLOYMENT.md              # Digital Ocean deployment guide
├── QUICKSTART.md              # 5-minute quick start
├── TESTING.md                 # Testing guide
└── CLAUDE.md                  # This file - AI assistant context
```

---

## Key Design Decisions

### 1. Dual Database Access Strategy
**Decision**: Use asyncpg for writes, SQLAlchemy for reads
**Rationale**:
- asyncpg's COPY is ~10x faster for bulk inserts (critical for real-time data)
- SQLAlchemy provides ORM benefits for complex queries
- Separate connection pools avoid contention
- API queries don't slow down data collection

### 2. Avoid Lazy Loading (Critical!)
**Decision**: Never use SQLAlchemy ORM objects that might trigger lazy loading
**Rationale**:
- Async SQLAlchemy + lazy loading = greenlet errors
- Solution: Select specific columns, not full objects
- Use manual object construction for responses
- This was the #1 cause of deployment issues

**Example (DO NOT DO)**:
```python
starlisting = await session.execute(select(Starlisting)).scalar_one()
name = starlisting.exchange.name  # ❌ Lazy load = greenlet error
```

**Example (CORRECT)**:
```python
# Select only the columns you need
result = await session.execute(
    select(Starlisting.id, Starlisting.active)
    .join(Exchange, ...)
)
starlisting_id, is_active = result.one()  # ✅ No objects, no lazy loading
```

### 3. 1-Minute Buffering for Funding/OI Data
**Decision**: Buffer funding/OI updates in memory, flush every 60 seconds
**Rationale**:
- **Storage Reduction**: 98.3% reduction (1,440 records/day vs 86,400 at per-second)
- **Database Performance**: Fewer writes, better query performance
- **Data Quality**: Latest value within each minute is preserved
- **Alignment**: Matches candle data granularity for easy JOINs
- **Timestamp Precision**: Minute-precision timestamps aligned to start of minute
- **Real-time Serving**: Will use Redis/cache for sub-minute data (future enhancement)

**Implementation**:
- Two in-memory buffers: `funding_buffer` and `oi_buffer` (dict keyed by coin)
- Background asyncio task: `_flush_loop()` runs every 60 seconds on minute boundary
- Overwrites within same minute: Latest WebSocket update wins
- Flush timestamp: `truncate_to_minute(utc_now())` for consistency

**Performance**:
- BTC + SOL at 1-second updates: ~172,800 records/day → 2,880 records/day (98.3% reduction)
- Projected storage: ~1.05 GB/year (vs ~15 GB/year at per-second)
- Query performance: BRIN indexes work efficiently on minute-precision data

### 4. COALESCE Pattern for Safe Backfills
**Decision**: Use COALESCE in ON CONFLICT to preserve existing complete data
**Rationale**:
- Backfills may provide incomplete data (e.g., funding_rate + premium only)
- Real-time collector captures all fields (including prices, OI, etc.)
- COALESCE prevents backfill from overwriting complete data with NULLs
- Safe to re-run backfills without data loss
- Pattern: `field = COALESCE(EXCLUDED.field, table.field)`

**Example**:
```sql
INSERT INTO funding_rates (...) VALUES (...)
ON CONFLICT (time, starlisting_id)
DO UPDATE SET
    funding_rate = COALESCE(EXCLUDED.funding_rate, funding_rates.funding_rate),
    premium = COALESCE(EXCLUDED.premium, funding_rates.premium),
    mark_price = COALESCE(EXCLUDED.mark_price, funding_rates.mark_price)
```

### 5. Starlisting Configuration
**Decision**: YAML config file synced to database
**Rationale**:
- Version-controlled configuration (YAML in git)
- Runtime flexibility (database for queries)
- Scripts trigger actions (sync, backfill) with explicit control
- Clean separation of config definition vs. runtime state

### 6. Docker Deployment
**Decision**: Single Dockerfile with Docker Compose orchestration
**Rationale**:
- Consistent environments (dev, staging, production)
- Easy deployment: `docker compose up -d`
- Automatic service dependencies and health checks
- Simple scaling: adjust replicas in compose file

### 7. TimescaleDB Hypertables
**Decision**: 1-day chunk intervals for all time-series tables
**Rationale**:
- Balance between query performance and metadata overhead
- Most queries are for recent data (hours to days)
- Automatic time-based partitioning
- Efficient data retention policies (future)

### 8. Trading Pairs (Coin + Quote)
**Decision**: Separate `quote_currencies` table instead of storing in `coins`
**Rationale**:
- BTC/USD ≠ BTC/USDC (different prices, liquidity, markets)
- Flexibility to add quote currencies without touching coins
- Clear data model: base asset (coin) + quote asset = trading pair
- Matches exchange API structure

---

## Configuration Management

### Environment Variables (.env)

**Database**:
```bash
POSTGRES_DB=kirby
POSTGRES_USER=kirby
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby
DATABASE_POOL_SIZE=20
```

**API**:
```bash
API_PORT=8000
ENVIRONMENT=production  # development | production
LOG_LEVEL=info
```

**Collectors**:
```bash
COLLECTOR_MAX_RETRIES=5
COLLECTOR_RESTART_DELAY=30
```

See [.env.example](.env.example) for all variables.

### Starlisting Configuration (config/starlistings.yaml)

Defines exchanges, coins, market types, and starlistings:

```yaml
exchanges:
  - name: hyperliquid
    display_name: Hyperliquid
    active: true

coins:
  - symbol: BTC
    name: Bitcoin
    active: true
  - symbol: SOL
    name: Solana
    active: true

quote_currencies:
  - symbol: USD
    name: US Dollar
    active: true

market_types:
  - name: perps
    display_name: Perpetuals
    active: true

starlistings:
  - exchange: hyperliquid
    coin: BTC
    quote: USD
    market_type: perps
    intervals: [1m, 15m, 4h, 1d]
    active: true
  - exchange: hyperliquid
    coin: SOL
    quote: USD
    market_type: perps
    intervals: [1m, 15m, 4h, 1d]
    active: true
```

**Sync to database**:
```bash
docker compose exec collector python -m scripts.sync_config
```

---

## Deployment

### Quick Start (Local or Server)

```bash
# 1. Clone and configure
git clone https://github.com/YOUR_USERNAME/kirby.git
cd kirby
cp .env.example .env
nano .env  # Set POSTGRES_PASSWORD

# 2. Deploy with one command
chmod +x deploy.sh
./deploy.sh
```

### Manual Deployment

```bash
# Build and start services
docker compose build
docker compose up -d

# Run migrations
docker compose exec collector alembic upgrade head

# Sync configuration
docker compose exec collector python -m scripts.sync_config

# Restart services
docker compose restart collector api

# Verify
docker compose ps
docker compose logs -f collector
```

### Digital Ocean Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete guide including:
- Droplet setup ($12-24/month)
- Security hardening (UFW, fail2ban, SSH)
- Backfill instructions (candles and funding/OI)
- Monitoring and backups
- Troubleshooting

---

## API Endpoints

**Base URL**: `http://localhost:8000`

### Available Endpoints

```
GET  /                          # Root - API information
GET  /health                    # Health check
GET  /starlistings              # List all starlistings
GET  /candles/{exchange}/{coin}/{quote}/{market_type}/{interval}
                                # Get candle data
```

### Examples

```bash
# Check API health
curl http://localhost:8000/health

# List all starlistings
curl http://localhost:8000/starlistings

# Get BTC/USD 1-minute candles (last 5)
curl "http://localhost:8000/candles/hyperliquid/BTC/USD/perps/1m?limit=5"

# Get SOL/USD 15-minute candles with time filter
curl "http://localhost:8000/candles/hyperliquid/SOL/USD/perps/15m?start_time=2025-10-26T00:00:00Z&limit=100"
```

### Response Format

```json
{
  "data": [
    {
      "time": "2025-10-26T19:41:00+00:00",
      "open": "113690.00000000",
      "high": "113690.00000000",
      "low": "113679.00000000",
      "close": "113680.00000000",
      "volume": "3.95787000",
      "num_trades": null
    }
  ],
  "metadata": {
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "interval": "1m",
    "count": 5
  }
}
```

**Interactive Docs**: http://localhost:8000/docs (Swagger UI)

---

## Data Export

Kirby provides comprehensive data export capabilities for AI/ML training, backtesting, and external analysis.

### Export Scripts

Four CLI scripts (`scripts/export_*.py`) export market data to CSV and Parquet formats:

1. **export_candles.py** - Export OHLCV candle data
   - Multi-interval support: `--intervals 1m`, `--intervals 1m,15m,4h`, or `--intervals all`
   - Outputs: time, open, high, low, close, volume, num_trades

2. **export_funding.py** - Export funding rate data
   - Outputs: time, funding_rate, premium, mark_price, index_price, oracle_price, mid_price, next_funding_time

3. **export_oi.py** - Export open interest data
   - Outputs: time, open_interest, notional_value, day_base_volume, day_notional_volume

4. **export_all.py** - Export merged datasets (RECOMMENDED FOR ML/BACKTESTING)
   - Merges candles + funding + OI aligned by timestamp
   - Multi-interval support
   - Missing values preserved as NULL (no forward-filling)
   - Perfect for ML training with complete market context

### Key Features

- **Both Formats**: CSV (universal) + Parquet (ML-optimized, ~10x smaller)
- **Flexible Time Ranges**: `--days 30` or `--start-time YYYY-MM-DD --end-time YYYY-MM-DD`
- **Metadata Files**: Each export generates `.json` metadata with parameters and stats
- **Docker Compatible**: Run inside container, exports saved to `exports/` directory

### Usage Examples

```bash
# Export BTC 1m candles (last 30 days, both formats)
docker compose exec collector python -m scripts.export_candles \
  --coin BTC --intervals 1m --days 30

# Export merged dataset for ML training (Parquet only)
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 90 --format parquet

# Export all intervals for multi-timeframe backtesting
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals all --days 365

# Export custom date range
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m \
  --start-time "2025-10-01" --end-time "2025-11-01"
```

### Merged Dataset Structure

`export_all.py` creates aligned time-series with:
- **Base**: Candle timestamps (e.g., 1m intervals)
- **LEFT JOIN**: Funding rates on time (1m buffered)
- **LEFT JOIN**: Open interest on time (1m buffered)
- **Null Strategy**: Missing values preserved as NULL

**Example merged row:**
```python
{
  "time": "2025-11-02 10:00:00",
  "open": 67500.50, "high": 67800.00, "low": 67400.25, "close": 67650.75,
  "volume": 1234.56, "num_trades": 542,
  "funding_rate": 0.000123, "premium": 0.5, "mark_price": 67650.00,
  "open_interest": 125000.50, "notional_value": 8456789.00
}
```

### ML Integration

**Pandas:**
```python
import pandas as pd
df = pd.read_parquet('exports/merged_hyperliquid_BTC_USD_perps_1m_*.parquet')
```

**PyTorch:**
```python
features = torch.tensor(df[['open', 'high', 'low', 'close', 'volume',
                             'funding_rate', 'open_interest']].values, dtype=torch.float32)
```

### Documentation

See **[docs/EXPORT.md](docs/EXPORT.md)** for:
- Complete command reference
- ML framework integration (PyTorch, TensorFlow, scikit-learn)
- Format comparison and best practices
- Troubleshooting guide

---

## Testing

### Test Suite

- **Total**: 54 tests (100% passing)
- **Unit Tests**: 26 tests (helper functions, validation)
- **Integration Tests**: 28 tests (API endpoints, repositories)
- **Coverage**: 49% (focused on critical paths)

### Run Tests

```bash
# Using test runner (recommended)
python scripts/run_tests.py

# Or directly with pytest
pytest                          # All tests
pytest tests/unit              # Unit tests only
pytest tests/integration       # Integration tests only
pytest --cov=src               # With coverage report
```

### Test Database

- Automatically created as `kirby_test`
- Isolated from production database
- Cleaned between test runs
- No manual setup required

See **[TESTING.md](TESTING.md)** for detailed testing guide.

---

## Operational Tasks

### Service Management

```bash
# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f                  # All services
docker compose logs -f collector        # Collector only
docker compose logs -f api              # API only

# Restart services
docker compose restart collector api

# Stop services
docker compose stop

# Full reset
docker compose down -v
```

### Database Operations

```bash
# Connect to database
docker compose exec timescaledb psql -U kirby -d kirby

# Run query
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles;"

# Run migrations
docker compose exec collector alembic upgrade head

# Create new migration
docker compose exec collector alembic revision --autogenerate -m "description"

# Check migration status
docker compose exec collector alembic current
```

### Configuration Management

```bash
# Sync YAML config to database
docker compose exec collector python -m scripts.sync_config

# Test collector with real data
docker compose exec collector python scripts/test_collector_simple.py

# Verify system
docker compose exec collector python scripts/test_full_system.py
```

### Backfill Operations

**Important**: All backfill commands must run **inside the Docker container** using `docker compose exec collector`.

#### Backfill Candles (CCXT)

```bash
# Backfill all active starlistings (365 days)
docker compose exec collector python -m scripts.backfill --days=365

# Backfill specific coin (BTC, 90 days)
docker compose exec collector python -m scripts.backfill --coin=BTC --days=90

# Backfill specific exchange
docker compose exec collector python -m scripts.backfill --exchange=hyperliquid --days=180
```

#### Backfill Funding Rates (Hyperliquid SDK)

```bash
# Backfill all active coins (365 days)
docker compose exec collector python -m scripts.backfill_funding --days=365

# Backfill specific coin (BTC, 30 days)
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=30

# Backfill using --all flag
docker compose exec collector python -m scripts.backfill_funding --all
```

**Hyperliquid API Limitations for Historical Funding Data**:
- ✅ Available: `funding_rate`, `premium`
- ❌ NOT available: `mark_price`, `oracle_price`, `mid_price`, `open_interest`, `next_funding_time`
- Real-time collector captures ALL fields going forward
- Backfill uses COALESCE to preserve existing complete data
- Safe to run multiple times without data loss

### Backup and Restore

```bash
# Backup database
docker compose exec -T timescaledb pg_dump -U kirby kirby | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore database
gunzip -c backup_20251026.sql.gz | docker compose exec -T timescaledb psql -U kirby -d kirby
```

---

## Development Guidelines

### Adding a New Exchange

1. **Create collector** in `src/collectors/{exchange_name}.py`:
   ```python
   from src.collectors.base import BaseCollector

   class NewExchangeCollector(BaseCollector):
       def __init__(self):
           super().__init__(exchange_name="new_exchange")

       async def connect(self):
           # Implement WebSocket connection
           pass

       async def collect(self):
           # Implement data collection loop
           pass
   ```

2. **Update config** in `config/starlistings.yaml`:
   ```yaml
   exchanges:
     - name: new_exchange
       display_name: New Exchange
       active: true

   starlistings:
     - exchange: new_exchange
       coin: BTC
       quote: USD
       market_type: spot
       intervals: [1m, 5m, 1h]
       active: true
   ```

3. **Register collector** in `src/collectors/main.py`:
   ```python
   from src.collectors.new_exchange import NewExchangeCollector

   manager.register_collector(NewExchangeCollector())
   ```

4. **Test and deploy**:
   ```bash
   python -m scripts.sync_config
   docker compose restart collector
   docker compose logs -f collector
   ```

### Adding a New Coin/Trading Pair

1. Update `config/starlistings.yaml`:
   ```yaml
   coins:
     - symbol: ETH
       name: Ethereum
       active: true

   starlistings:
     - exchange: hyperliquid
       coin: ETH
       quote: USD
       market_type: perps
       intervals: [1m, 15m, 4h]
       active: true
   ```

2. Sync and restart:
   ```bash
   docker compose exec collector python -m scripts.sync_config
   docker compose restart collector
   ```

### Code Quality Standards

- **Type hints**: All functions must have complete type hints
- **Async/await**: Use async for all I/O operations
- **Error handling**: Never silently fail; log errors with full context
- **Testing**: Write tests for all new features (unit + integration)
- **Logging**: Use structured logging (JSON format in production)
- **Validation**: Pydantic for all external data
- **Documentation**: Update docs when changing behavior

### Code Formatting

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy src
```

---

## Common Issues and Solutions

### Issue: Greenlet Errors

**Error**: `MissingGreenlet: greenlet_spawn has not been called`

**Cause**: Accessing SQLAlchemy ORM relationships in async context (lazy loading)

**Solution**:
- Select only columns you need: `select(Model.id, Model.name)`
- Don't load full ORM objects
- Manually construct response objects

### Issue: Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'src.config'`

**Solution**: Use module syntax: `python -m scripts.sync_config` (not `python scripts/sync_config.py`)

### Issue: Database Connection Errors

**Error**: `relation "exchanges" does not exist`

**Cause**: Migrations haven't been run yet

**Solution**:
```bash
docker compose exec collector alembic upgrade head
docker compose restart collector api
```

### Issue: No Data Collecting

**Symptoms**: API returns empty candles array

**Debugging**:
```bash
# Check collector logs
docker compose logs -f collector

# Verify starlistings
curl http://localhost:8000/starlistings

# Check database
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles;"

# Restart collector
docker compose restart collector
```

### Issue: Backfill Script Hangs

**Symptoms**: Script logs "Database connections closed" but doesn't return to command line

**Cause**: WebSocket connection not being closed properly

**Solution**: Scripts now include explicit WebSocket cleanup in finally blocks. If you encounter this:
- Press Ctrl+C to exit
- Check database - data was likely stored successfully
- Verify with: `docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM funding_rates;"`

---

## Performance Considerations

### Database Query Optimization

- **Use indexes**: Queries on `(starlisting_id, time)` are fast
- **Limit results**: Always use `LIMIT` clause in queries
- **Time filters**: Use `start_time` and `end_time` filters
- **BRIN index**: Efficient for time-based queries
- **Minute-precision**: All time-series tables use minute-precision for efficient indexing

### Collector Performance

- **Bulk upsert**: ~10x faster than individual inserts
- **Connection pooling**: Reuse connections, don't create new ones
- **Async operations**: Never block the event loop
- **Error handling**: Graceful reconnection on failures
- **1-minute buffering**: Reduces database writes by 98.3% for funding/OI data

### API Performance

- **Connection pooling**: SQLAlchemy pool (20 connections default)
- **Avoid N+1 queries**: Eager load relationships when needed
- **Response streaming**: For large datasets (future enhancement)
- **Caching**: Redis for frequently accessed data (future enhancement)

---

## Monitoring and Observability

### Key Metrics to Monitor

- **Data freshness**: Time since last candle/funding/OI per starlisting
- **Collection lag**: Delay between exchange time and ingestion
- **API latency**: Response time percentiles (P50, P95, P99)
- **Error rates**: Failed requests, collector crashes
- **Throughput**: Candles/second ingested, requests/second served
- **Database size**: Monitor disk usage and growth rate
- **Buffer flush**: Check logs for "Flushed buffers to database" every minute

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database connectivity
docker compose exec timescaledb pg_isready -U kirby

# Service status
docker compose ps

# Resource usage
docker stats

# Check funding/OI collection
docker compose logs collector | grep "Flushed buffers"
```

### Logging

- **Format**: JSON in production, pretty-print in development
- **Levels**: DEBUG (dev), INFO (prod), ERROR (always)
- **Structure**: Timestamp, level, logger, event, context
- **Rotation**: Automatic log rotation via Docker

---

## Security Best Practices

### Implemented Security Measures

✅ **Environment Variables**: Secrets in `.env` file (not in code)
✅ **Non-root Container**: Runs as user `kirby` (UID 1000)
✅ **Input Validation**: Pydantic validates all inputs
✅ **SQL Injection Protection**: SQLAlchemy parameterized queries
✅ **Database Isolation**: Internal Docker network only
✅ **CORS Configuration**: Configurable allowed origins

### Recommended Production Security

- **Firewall**: Configure UFW (see DEPLOYMENT.md)
- **Fail2ban**: Intrusion prevention
- **SSH Hardening**: Key-only auth, custom port
- **SSL/TLS**: Use reverse proxy (Nginx) with Let's Encrypt
- **Database**: Internal network only, no public exposure
- **Secrets**: Use secrets management (HashiCorp Vault, AWS Secrets Manager)

---

## Future Enhancements

### Planned Features

- **WebSocket API**: Real-time streaming to clients (with Redis for sub-minute data)
- **Caching Layer**: Redis for frequently accessed data and real-time serving
- **More Exchanges**: Binance, Coinbase, OKX, etc.
- **More Data Types**: Order book depth, trade tape
- **Advanced Monitoring**: Prometheus metrics, Grafana dashboards
- **Data Retention**: Automatic cleanup of old data
- **Multi-region**: Geographic distribution for lower latency
- **Rate Limiting**: API rate limits per client
- **Authentication**: API keys for authenticated access
- **Funding/OI API Endpoints**: Dedicated endpoints for funding and OI data

---

## Important Notes

### Database URL Formats

- **asyncpg (application)**: `postgresql+asyncpg://user:pass@host:port/db`
- **psycopg2 (Alembic)**: `postgresql://user:pass@host:port/db`
- Alembic automatically handles the conversion

### Hyperliquid Specifics

**Data Collection**:
- **WebSocket (Candles)**: Real-time OHLCV updates
- **WebSocket (Funding/OI)**: Real-time via `activeAssetCtx` subscription (1-minute buffering)
- **Historical API (Candles)**: Via CCXT library
- **Historical API (Funding)**: Via Hyperliquid SDK `funding_history()` - **LIMITED DATA**

**Intervals**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 12h, 1d, 1w, 1M

**Rate Limits**: Respectful rate limiting built-in

**Market Type**: Perpetuals (perps) only

#### CRITICAL: USD vs USDC Quote Currency

**The Issue**: Hyperliquid displays "USD" in their UI but actually settles all perpetual contracts in **USDC**.

**API Behavior**:
- **Hyperliquid SDK**: Uses coin symbol only (e.g., `"BTC"`) - quote/settlement currency is implicit (USDC)
- **CCXT Library**: Uses explicit format `BTC/USDC:USDC` - clearly shows USDC settlement
- **WebSocket Data**: Returns coin symbol only (e.g., `"coin": "BTC"`)

**Our Implementation Decision**:
- **Database Storage**: We use `"USD"` as the quote currency symbol (matching Hyperliquid's UI/marketing)
- **Interpretation**: Treat `USD` as an **alias** for `USDC` when working with Hyperliquid
- **Rationale**:
  - Matches how Hyperliquid presents data to users
  - Simpler for end users (BTC/USD is more intuitive than BTC/USDC)
  - Doesn't affect functionality since we're only collecting Hyperliquid perps
  - If adding spot markets in future, we'll need to distinguish USD vs USDC

**When Writing Integration Code**:
- **SDK calls**: Use just coin symbol (`info.funding_history('BTC')`)
- **CCXT calls**: Map `USD` → `USDC` (use `BTC/USDC:USDC` format)
- **Database queries**: Use `quote_currency = "USD"` (our internal representation)
- **Documentation**: Clarify that Hyperliquid "USD" perpetuals settle in USDC stablecoin

**Example Mapping**:
```python
# Our database
coin = "BTC"
quote = "USD"  # Stored in DB

# For CCXT API calls
if exchange == "hyperliquid" and quote == "USD":
    ccxt_quote = "USDC"
    ccxt_symbol = f"{coin}/{ccxt_quote}:{ccxt_quote}"  # BTC/USDC:USDC

# For Hyperliquid SDK calls
if exchange == "hyperliquid":
    # Just use coin symbol, quote is implicit
    funding = info.funding_history(coin)  # "BTC"
```

#### Hyperliquid API Limitations

**Historical Funding Data** (`info.funding_history()`):
- ✅ **Available**: `funding_rate`, `premium`
- ❌ **NOT Available**: `mark_price`, `index_price`, `oracle_price`, `mid_price`, `next_funding_time`
- Updates: Hourly (24 records/day per coin)

**Real-time Funding/OI Data** (WebSocket `activeAssetCtx`):
- ✅ **Available**: ALL fields including prices and open interest
- Updates: ~Every second
- Storage: Buffered to 1-minute intervals (98.3% storage reduction)

**No Historical Open Interest**:
- Hyperliquid API does not provide historical OI data
- Only real-time OI available via WebSocket
- Backfill script only handles funding rates

### TimescaleDB Specifics

- **Chunk Interval**: 1 day (configurable via `TIMESCALE_CHUNK_TIME_INTERVAL`)
- **Compression**: Not yet enabled (future optimization)
- **Retention Policy**: Manual for now (automatic in future)
- **Continuous Aggregates**: Not yet implemented (future for computed intervals)
- **Hypertables**: candles, funding_rates, open_interest

### Docker Compose Dependencies

- `timescaledb` must be healthy before other services start
- `collector` and `api` depend on `timescaledb`
- Health checks ensure proper startup order
- Restart policies: `unless-stopped` for resilience

---

## Quick Reference

### Essential Commands

```bash
# Deployment
./deploy.sh                                         # One-command deploy
docker compose up -d                                # Start services
docker compose restart collector api                # Restart after config changes

# Migrations
docker compose exec collector alembic upgrade head  # Run migrations
docker compose exec collector alembic current       # Check migration status

# Configuration
docker compose exec collector python -m scripts.sync_config  # Sync YAML to DB

# Backfill (must run inside Docker container)
docker compose exec collector python -m scripts.backfill --days=365  # Candles
docker compose exec collector python -m scripts.backfill_funding --days=365  # Funding

# Monitoring
docker compose logs -f collector                    # Watch collector logs
curl http://localhost:8000/health                   # Check API health
docker stats                                        # Resource usage

# Database
docker compose exec timescaledb psql -U kirby -d kirby  # Connect to DB
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles;"
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM funding_rates;"

# Testing
python scripts/run_tests.py                         # Run all tests
```

### Key URLs (when running)

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Starlistings**: http://localhost:8000/starlistings

### Important Files

- **[README.md](README.md)**: User documentation
- **[DEPLOYMENT.md](DEPLOYMENT.md)**: Production deployment guide
- **[QUICKSTART.md](QUICKSTART.md)**: 5-minute quick start
- **[TESTING.md](TESTING.md)**: Testing guide
- **[docker-compose.yml](docker-compose.yml)**: Service definitions
- **[config/starlistings.yaml](config/starlistings.yaml)**: Starlisting config
- **[.env.example](.env.example)**: Environment variable template
- **[docs/HYPERLIQUID_API_REFERENCE.md](docs/HYPERLIQUID_API_REFERENCE.md)**: Hyperliquid API details

---

## Project Status

**✅ Complete and Production-Ready**

### Completed Phases

- ✅ **Phase 1**: Foundation - Database schema, models, repositories
- ✅ **Phase 2**: Configuration - YAML management, sync scripts
- ✅ **Phase 3**: Data Collection - Hyperliquid WebSocket collectors (candles + funding/OI)
- ✅ **Phase 4**: API Layer - FastAPI endpoints for querying data
- ✅ **Phase 5**: Testing - 54 tests (100% passing)
- ✅ **Phase 6**: Deployment - Docker, Digital Ocean guide
- ✅ **Phase 7**: Production - Successfully collecting real data
- ✅ **Phase 8**: 1-Minute Buffering - Optimized funding/OI storage (98.3% reduction)
- ✅ **Phase 9**: Backfill System - Historical data for candles and funding rates

### Deployment Status

- **Environment**: Digital Ocean Droplet
- **Status**: Live and collecting data
- **Uptime**: Since October 26, 2025
- **Data Collection**: Real-time candles, funding rates, and open interest from Hyperliquid
- **Starlistings**: 8 active (BTC/SOL × USD × perps × 4 intervals)
- **Tests**: 54/54 passing
- **Storage Optimization**: 1-minute buffering implemented for funding/OI data

### Current Capabilities

✅ **Real-time Data Collection**:
- OHLCV candles (1m, 15m, 4h, 1d)
- Funding rates (1-minute intervals with buffering)
- Open interest (1-minute intervals with buffering)

✅ **Historical Data Backfill**:
- Candles via CCXT (all intervals)
- Funding rates via Hyperliquid SDK (limited fields)

✅ **Storage Optimization**:
- 98.3% storage reduction for funding/OI data
- Minute-precision timestamps aligned across all tables
- COALESCE pattern prevents data loss during backfills

✅ **Production Features**:
- Docker deployment with health checks
- Structured logging with context
- Automatic reconnection on failures
- Connection pooling for performance
- Comprehensive error handling

### Known Limitations

- Single exchange (Hyperliquid) - more exchanges planned
- No funding/OI API endpoints yet - data collected and stored only
- No WebSocket API - REST only
- No authentication - public API
- No rate limiting - unlimited requests
- Historical funding data incomplete (funding_rate + premium only)
- No historical open interest data available

---

## Contact & Collaboration

This project was built collaboratively with senior engineering oversight and AI assistance (Claude). The codebase follows industry best practices and is designed for production use.

**Last Updated**: November 2, 2025
**Version**: 1.1.0 - Production with 1-Minute Buffering
**Status**: ✅ Deployed and collecting real-time candles, funding, and OI data
**Next Steps**: Add funding/OI API endpoints, Redis caching for real-time serving, expand to more exchanges

---

**Happy Trading!** 📈🚀
