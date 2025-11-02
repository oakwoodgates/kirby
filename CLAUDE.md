# Kirby Project Documentation

> **Project Name**: Kirby
> **Inspiration**: Nintendo character that inhales unlimited objects
> **Purpose**: Ingest real-time and historical market data from multiple exchanges, serve via REST API
> **Status**: ✅ **Production Ready** - All phases complete, deployed and collecting data

---

## Overview

Kirby is a high-performance market data ingestion and API system for cryptocurrency exchanges. It collects OHLCV candle data in real-time via WebSocket connections and serves it via a FastAPI REST API to downstream applications (charting tools, AI/ML models, trading bots).

**Current Deployment**: Successfully deployed on Digital Ocean, collecting real-time data from Hyperliquid exchange.

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
2. **High Performance**: Async I/O, optimized bulk inserts via asyncpg COPY, connection pooling
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
Real-time Collection:
Hyperliquid WebSocket → Collector → asyncpg (COPY/upsert) → TimescaleDB

API Queries:
Client Apps → FastAPI → SQLAlchemy (read) → TimescaleDB → JSON Response

Configuration:
YAML (starlistings.yaml) → sync_config.py → Database tables
```

### Service Architecture

```
┌─────────────────────────────────────────────────┐
│  Docker Compose Orchestration                   │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌────────────────┐  ┌──────────────────────┐  │
│  │  TimescaleDB   │◄─┤  Kirby Collector     │  │
│  │  (PostgreSQL)  │  │  (WebSocket client)  │  │
│  │  Port: 5432    │  │  Background service  │  │
│  └────────┬───────┘  └──────────────────────┘  │
│           │                                     │
│           │          ┌──────────────────────┐  │
│           └─────────►│  Kirby API           │  │
│                      │  (FastAPI/Uvicorn)   │  │
│                      │  Port: 8000          │  │
│                      └──────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
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
- ON CONFLICT: Upsert support for reprocessing/backfill

### Database Access Patterns

**Writes** (high-performance via asyncpg):
- Collectors use asyncpg pool directly
- Bulk upsert: `INSERT ... ON CONFLICT (time, starlisting_id) DO UPDATE`
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
│   │       ├── health.py      # Health check endpoints
│   │       └── starlistings.py # Starlisting endpoints
│   ├── collectors/             # Data collection services
│   │   ├── base.py            # BaseCollector abstract class
│   │   ├── hyperliquid.py     # Hyperliquid WebSocket collector
│   │   └── main.py            # CollectorManager orchestrator
│   ├── db/                     # Database layer
│   │   ├── base.py            # SQLAlchemy Base, naming conventions
│   │   ├── models.py          # ORM models (Exchange, Coin, Starlisting, Candle)
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
│       ├── helpers.py         # Timestamp conversion, validation
│       └── logging.py         # Structured logging setup
├── tests/
│   ├── conftest.py            # Shared fixtures (test DB, client)
│   ├── unit/                  # Unit tests (26 tests)
│   │   └── test_helpers.py    # Helper function tests
│   └── integration/           # Integration tests (28 tests)
│       ├── test_api_*.py      # API endpoint tests
│       └── test_repositories.py # Repository tests
├── scripts/                    # Operational scripts
│   ├── sync_config.py         # Sync YAML config to database
│   ├── test_collector_simple.py # Test real data collection
│   ├── test_full_system.py    # System verification
│   └── run_tests.py           # Test runner with DB setup
├── config/                     # Configuration files
│   └── starlistings.yaml      # Starlisting definitions
├── migrations/                 # Alembic migrations
│   ├── env.py                 # Async migration environment
│   └── versions/              # Migration files
│       └── 20251026_0001_initial_schema.py # Initial working schema
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

### 3. Starlisting Configuration
**Decision**: YAML config file synced to database
**Rationale**:
- Version-controlled configuration (YAML in git)
- Runtime flexibility (database for queries)
- Scripts trigger actions (sync, backfill) with explicit control
- Clean separation of config definition vs. runtime state

### 4. Docker Deployment
**Decision**: Single Dockerfile with Docker Compose orchestration
**Rationale**:
- Consistent environments (dev, staging, production)
- Easy deployment: `docker compose up -d`
- Automatic service dependencies and health checks
- Simple scaling: adjust replicas in compose file

### 5. TimescaleDB Hypertables
**Decision**: 1-day chunk intervals for candles table
**Rationale**:
- Balance between query performance and metadata overhead
- Most queries are for recent data (hours to days)
- Automatic time-based partitioning
- Efficient data retention policies (future)

### 6. Trading Pairs (Coin + Quote)
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

---

## Performance Considerations

### Database Query Optimization

- **Use indexes**: Queries on `(starlisting_id, time)` are fast
- **Limit results**: Always use `LIMIT` clause in queries
- **Time filters**: Use `start_time` and `end_time` filters
- **BRIN index**: Efficient for time-based queries

### Collector Performance

- **Bulk upsert**: ~10x faster than individual inserts
- **Connection pooling**: Reuse connections, don't create new ones
- **Async operations**: Never block the event loop
- **Error handling**: Graceful reconnection on failures

### API Performance

- **Connection pooling**: SQLAlchemy pool (20 connections default)
- **Avoid N+1 queries**: Eager load relationships when needed
- **Response streaming**: For large datasets (future enhancement)
- **Caching**: Redis for frequently accessed data (future enhancement)

---

## Monitoring and Observability

### Key Metrics to Monitor

- **Data freshness**: Time since last candle per starlisting
- **Collection lag**: Delay between exchange time and ingestion
- **API latency**: Response time percentiles (P50, P95, P99)
- **Error rates**: Failed requests, collector crashes
- **Throughput**: Candles/second ingested, requests/second served
- **Database size**: Monitor disk usage and growth rate

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

### Planned Features (Not in MVP)

- **WebSocket API**: Real-time streaming to clients
- **Caching Layer**: Redis for frequently accessed data
- **More Exchanges**: Binance, Coinbase, OKX, etc.
- **More Data Types**: Order book, trades, funding rates, open interest
- **Advanced Monitoring**: Prometheus metrics, Grafana dashboards
- **Data Retention**: Automatic cleanup of old data
- **Multi-region**: Geographic distribution for lower latency
- **Rate Limiting**: API rate limits per client
- **Authentication**: API keys for authenticated access

---

## Important Notes

### Database URL Formats

- **asyncpg (application)**: `postgresql+asyncpg://user:pass@host:port/db`
- **psycopg2 (Alembic)**: `postgresql://user:pass@host:port/db`
- Alembic automatically handles the conversion

### Hyperliquid Specifics

- **WebSocket**: Real-time candle updates (primary data source)
- **Intervals**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 12h, 1d, 1w, 1M
- **Rate Limits**: Respectful rate limiting built-in
- **Market Type**: Perpetuals (perps) only

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

### TimescaleDB Specifics

- **Chunk Interval**: 1 day (configurable via `TIMESCALE_CHUNK_TIME_INTERVAL`)
- **Compression**: Not yet enabled (future optimization)
- **Retention Policy**: Manual for now (automatic in future)
- **Continuous Aggregates**: Not yet implemented (future for computed intervals)

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

# Monitoring
docker compose logs -f collector                    # Watch collector logs
curl http://localhost:8000/health                   # Check API health
docker stats                                        # Resource usage

# Database
docker compose exec timescaledb psql -U kirby -d kirby  # Connect to DB
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM candles;"

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

---

## Project Status

**✅ Complete and Production-Ready**

### Completed Phases

- ✅ **Phase 1**: Foundation - Database schema, models, repositories
- ✅ **Phase 2**: Configuration - YAML management, sync scripts
- ✅ **Phase 3**: Data Collection - Hyperliquid WebSocket collector
- ✅ **Phase 4**: API Layer - FastAPI endpoints for querying data
- ✅ **Phase 5**: Testing - 54 tests (100% passing)
- ✅ **Phase 6**: Deployment - Docker, Digital Ocean guide
- ✅ **Phase 7**: Production - Successfully collecting real data

### Deployment Status

- **Environment**: Digital Ocean Droplet
- **Status**: Live and collecting data
- **Uptime**: Since October 26, 2025
- **Data Collection**: Real-time from Hyperliquid
- **Starlistings**: 8 active (BTC/SOL × USD × perps × 4 intervals)
- **Tests**: 54/54 passing

### Known Limitations

- Single exchange (Hyperliquid) - more exchanges planned
- No backfill system yet - only real-time collection
- No WebSocket API - REST only
- No authentication - public API
- No rate limiting - unlimited requests

---

## Contact & Collaboration

This project was built collaboratively with senior engineering oversight and AI assistance (Claude). The codebase follows industry best practices and is designed for production use.

**Last Updated**: October 26, 2025
**Version**: 1.0.0 - Production Release
**Status**: ✅ Deployed and collecting real-time data
**Next Steps**: Monitor stability, add more exchanges and features

---

**Happy Trading!** 📈🚀
