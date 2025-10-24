# Kirby

A lightweight, secure, and modular cryptocurrency data ingestion platform and API built with Python, FastAPI, TimescaleDB, and CCXT.

## Overview

Kirby ingests real-time and historical cryptocurrency market data from multiple exchanges (starting with Hyperliquid, expandable to Binance, Coinbase, and more). Data is stored in TimescaleDB and exposed via a RESTful API for consumption by trading applications, charting tools, and analytics platforms.

### Key Features

✅ **Modular Architecture** - CCXT for standardized exchange integration + support for custom integrations
✅ **High-Performance Writes** - asyncpg for fast data ingestion (50K+ inserts/sec)
✅ **Flexible Queries** - SQLAlchemy 2.0 async for complex API queries
✅ **Time-Series Optimized** - TimescaleDB hypertables with automatic partitioning and compression
✅ **Real-Time Data** - WebSocket-based collectors with auto-reconnection and gap detection
✅ **Historical Backfill** - Automatic backfill of all available historical data when adding new listings
✅ **Composable Listings** - Exchange + Coin + Type (perps/spot/futures) model
✅ **Production-Ready** - Docker Compose deployment, structured logging, health monitoring

## Project Structure

```
kirby/
├── src/
│   ├── api/                      # FastAPI application (Phase 5)
│   ├── backfill/                 # Historical data backfill ✅
│   │   ├── base.py               # Abstract backfiller
│   │   └── hyperliquid_backfiller.py
│   ├── collectors/               # Real-time data collectors ✅
│   │   ├── base.py               # Abstract collector with CCXT
│   │   ├── hyperliquid_websocket.py  # WebSocket collector
│   │   └── hyperliquid_polling.py    # REST fallback
│   ├── models/                   # SQLAlchemy 2.0 async models ✅
│   │   ├── base.py
│   │   ├── exchange.py, coin.py, listing_type.py, listing.py
│   │   ├── candle.py, funding_rate.py, open_interest.py
│   │   ├── trade.py, market_metadata.py
│   │   └── backfill_job.py
│   ├── schemas/                  # Pydantic v2 schemas ✅
│   │   ├── candle.py, funding_rate.py, open_interest.py
│   │   ├── listing.py, trade.py, market_metadata.py
│   │   └── __init__.py
│   ├── db/                       # Database layer ✅
│   │   ├── asyncpg_pool.py       # Connection pool (writes)
│   │   ├── session.py            # SQLAlchemy session (reads)
│   │   └── writer.py             # DataWriter (batch UPSERT)
│   ├── config/                   # Configuration ✅
│   │   ├── settings.py           # Pydantic Settings
│   │   └── __init__.py
│   └── utils/                    # Utilities ✅
│       ├── logger.py             # Structured logging
│       └── __init__.py
├── migrations/                   # Alembic migrations ✅
│   └── versions/
│       ├── 20251024_0017_ef041ce476ce_initial_schema_with_all_tables.py
│       └── 20251024_1056_33cd00d7748f_add_backfill_tracking_table.py
├── scripts/                      # CLI utilities ✅
│   ├── seed_database.py          # Seed initial data
│   ├── test_collectors.py        # Test WebSocket collectors
│   ├── run_backfill.py           # Production backfill orchestrator
│   └── test_backfill.py          # Test backfill service
├── docker-compose.yml            # TimescaleDB container ✅
├── alembic.ini                   # Alembic config ✅
├── pyproject.toml                # Poetry dependencies ✅
├── .env                          # Environment variables ✅
├── README.md                     # This file
├── ARCHITECTURE.md               # Architecture documentation ✅
└── DEPLOYMENT.md                 # Deployment guide ✅
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI + Gunicorn + Uvicorn | High-performance async REST API |
| **Database** | TimescaleDB (PostgreSQL) | Time-series optimized storage |
| **ORM (Reads)** | SQLAlchemy 2.0 async | Complex queries, relationships |
| **DB Driver (Writes)** | asyncpg | High-performance inserts (3-5x faster) |
| **Exchange Integration** | CCXT (WebSocket + REST) | Unified API for 100+ exchanges |
| **Validation** | Pydantic v2 | Type-safe schemas and settings |
| **Migrations** | Alembic | Database schema versioning |
| **Process Management** | Docker + asyncio | Collector orchestration |
| **Deployment** | Docker Compose | Container orchestration |

## Data Model

### Core Entities

**Listing** = Exchange + Coin + Type (e.g., Hyperliquid + BTC + Perps)

### Database Schema

#### Relational Tables (Reference Data)
- `exchanges` - Supported exchanges (Hyperliquid, Binance, etc.)
- `coins` - Cryptocurrencies (BTC, HYPE, ETH, etc.)
- `listing_types` - Trading types (perps, spot, futures, options)
- `listings` - Tradeable markets (combination of above)

#### Hypertables (Time-Series Data)
- `candles` - OHLCV data (1m, 5m, 15m, 1h, 4h, 1d)
- `funding_rates` - Funding rates for perpetuals
- `open_interest` - Open interest snapshots
- `trades` - Individual trades (optional, high-volume)
- `market_metadata` - Ticker snapshots (bid/ask, volume, 24h stats)

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Poetry (recommended) or pip

### Installation

1. **Clone the repository**
```bash
git clone <repo-url>
cd kirby
```

2. **Install dependencies**
```bash
# Using Poetry (recommended)
poetry install

# Activate the Poetry shell
poetry shell
```

3. **Configure environment**
```bash
# .env file already exists with sensible defaults
# Review and edit if needed (database credentials, API settings)
nano .env
```

4. **Start TimescaleDB**
```bash
# Start TimescaleDB container
docker-compose up -d

# Verify container is running
docker ps
```

5. **Run database migrations**
```bash
# Run all migrations (creates tables, hypertables, indexes)
alembic upgrade head

# Verify tables were created
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "\dt"
```

6. **Seed initial data**
```bash
# Seeds Hyperliquid exchange and BTC/HYPE listings
python scripts/seed_database.py
```

7. **Test data collectors** (optional)
```bash
# Test WebSocket collectors for BTC and HYPE
# This will run for 3 minutes and collect real-time data
bash -c "PYTHONPATH=. python scripts/test_collectors.py"

# Verify data is being collected
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT COUNT(*) FROM candle;"
```

8. **Run historical backfill** (optional)
```bash
# Backfill last 30 days of data for BTC and HYPE
python scripts/run_backfill.py

# Or test with just 3 days
python scripts/test_backfill.py
```

9. **Start the API server** (Phase 5 - Coming Soon)
```bash
# Development mode with auto-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode with Gunicorn
gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Verify Installation

```bash
# Check database tables
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "\dt"

# Check candle data
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT listing_id, COUNT(*) as count, MIN(timestamp) as earliest, MAX(timestamp) as latest FROM candle GROUP BY listing_id;"

# Check funding rates
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT listing_id, COUNT(*) as count FROM funding_rate GROUP BY listing_id;"

# Check open interest
docker exec kirby_timescaledb psql -U kirby_user -d kirby -c "SELECT listing_id, COUNT(*) as count FROM open_interest GROUP BY listing_id;"
```

## Architecture

### Hybrid Database Layer

**asyncpg for Writes** (Data Collectors → Database)
- 3-5x faster than SQLAlchemy for bulk inserts
- Direct PostgreSQL protocol
- Batch inserts with ON CONFLICT handling

**SQLAlchemy for Reads** (API → Database)
- Complex queries with filters, joins, aggregations
- Type-safe ORM with relationships
- Automatic query optimization

### Data Collection Flow

```
Exchange (WebSocket)
    ↓
CCXTCollector (normalize data)
    ↓
DataWriter (asyncpg batch insert)
    ↓
TimescaleDB Hypertable
    ↓
API (SQLAlchemy queries)
    ↓
Client Application
```

### Collector Manager (asyncio)

- Spawns one collector per active listing
- Automatic reconnection with exponential backoff
- Health monitoring (heartbeat every 30s)
- Graceful shutdown on SIGTERM/SIGINT
- Gap detection and backfill triggers

## API Endpoints (Planned)

### Listings
- `POST /api/v1/listings` - Create new listing (triggers backfill)
- `GET /api/v1/listings` - List all listings
- `GET /api/v1/listings/{id}` - Get listing details
- `PATCH /api/v1/listings/{id}` - Update listing config
- `DELETE /api/v1/listings/{id}` - Deactivate listing

### Market Data
- `GET /api/v1/candles` - Query candles with filters
- `GET /api/v1/funding-rates` - Query funding rates
- `GET /api/v1/open-interest` - Query open interest
- `GET /api/v1/market-snapshot` - Latest data for all listings

### WebSocket Streaming
- `WS /api/v1/stream/candles/{listing_id}` - Real-time candles
- `WS /api/v1/stream/tickers` - Real-time ticker updates

### Health & Monitoring
- `GET /api/v1/health` - Overall system health
- `GET /api/v1/health/collectors` - Per-collector status
- `GET /api/v1/health/database` - Database stats

## Development Status

### ✅ Phase 1: Foundation (Completed)
- [x] Project structure and Poetry setup
- [x] Pydantic Settings configuration
- [x] Structured logging (JSON + text formats)
- [x] SQLAlchemy 2.0 async models (9 tables)
- [x] Alembic migrations setup
- [x] Database session management

### ✅ Phase 2: Database Layer (Completed)
- [x] asyncpg connection pool (10-20 connections)
- [x] DataWriter class with batch UPSERT operations
- [x] Pydantic v2 schemas for all data types
- [x] Docker Compose configuration with TimescaleDB
- [x] Initial migration (all 9 tables created)
- [x] TimescaleDB hypertables (candles, funding_rates, open_interest, trades, market_metadata)
- [x] Compression policies (7-day chunks, compressed after 7 days)
- [x] Database seeding (Hyperliquid exchange, BTC/HYPE listings)

### ✅ Phase 3: Real-Time Data Collection (Completed)
- [x] BaseCollector abstract class with CCXT integration
- [x] HyperliquidWebSocketCollector (Hyperliquid Python SDK)
- [x] HyperliquidPollingCollector (CCXT REST fallback)
- [x] WebSocket channels: candles (1m), l2Book, activeAssetCtx (funding/OI)
- [x] Thread-safe async execution (asyncio.run_coroutine_threadsafe)
- [x] Automatic reconnection with exponential backoff
- [x] Health monitoring with heartbeats (30s intervals)
- [x] Real-time data verified in TimescaleDB

### ✅ Phase 4: Historical Backfill Service (Completed)
- [x] BaseBackfiller abstract class
- [x] HyperliquidBackfiller with CCXT REST API
- [x] Backfill tracking table (backfill_job)
- [x] Batch processing (500-1000 records per request)
- [x] Rate limiting (configurable delays)
- [x] Progress monitoring and error handling
- [x] Orchestrator script (run_backfill.py)
- [x] Successfully tested: 4,320 candles in 16 seconds

### 📋 Phase 5: FastAPI REST API (Next Priority)
- [ ] API foundation (main.py, dependencies, middleware)
- [ ] Health endpoints (system, database, collectors)
- [ ] Candles endpoint with filters and pagination
- [ ] Funding rates endpoint
- [ ] Open interest endpoint
- [ ] Listings CRUD endpoints
- [ ] Market snapshot endpoint
- [ ] Query optimization with SQLAlchemy
- [ ] OpenAPI/Swagger documentation
- [ ] Integration tests

### 📋 Phase 6: Production Deployment (Planned)
- [x] Docker Compose configuration
- [x] Environment configuration (.env)
- [ ] Multi-stage Dockerfiles (optimized)
- [ ] Production deployment to Digital Ocean
- [ ] Nginx reverse proxy setup
- [ ] SSL/TLS certificates (Let's Encrypt)
- [ ] Monitoring and alerting (logs, metrics)
- [ ] Automated backups (pg_dump + S3)
- [ ] CI/CD pipeline (GitHub Actions)

## Configuration

All configuration is managed via environment variables (loaded from `.env`):

### Database
- `DATABASE_URL` - SQLAlchemy async URL
- `ASYNCPG_URL` - asyncpg connection URL
- `DB_POOL_MIN_SIZE` - Min connection pool size (default: 10)
- `DB_POOL_MAX_SIZE` - Max connection pool size (default: 20)

### API
- `API_HOST` - API server host (default: 0.0.0.0)
- `API_PORT` - API server port (default: 8000)
- `API_WORKERS` - Gunicorn worker count (default: 4)
- `CORS_ORIGINS` - Allowed CORS origins (JSON array)

### Collectors
- `COLLECTOR_HEARTBEAT_INTERVAL` - Heartbeat interval in seconds (default: 30)
- `COLLECTOR_RECONNECT_DELAY` - Initial reconnect delay (default: 5)
- `COLLECTOR_MAX_RECONNECT_ATTEMPTS` - Max reconnection attempts (default: 10)

### Backfill
- `BACKFILL_BATCH_SIZE` - Candles per request (default: 1000)
- `BACKFILL_RATE_LIMIT_DELAY` - Delay between requests in ms (default: 1000)

## Deployment

### Digital Ocean Droplet (Recommended for Phase 1-2)

**Specs:** 4-8GB RAM, 2-4 vCPUs (~$24-48/month)

```bash
# 1. SSH into droplet
ssh root@your-droplet-ip

# 2. Install Docker & Docker Compose
apt update && apt install docker.io docker-compose -y

# 3. Clone repo and configure
git clone <repo-url> /opt/kirby
cd /opt/kirby
cp .env.example .env
nano .env  # Edit configuration

# 4. Start services
docker-compose up -d

# 5. Run migrations
docker-compose exec api alembic upgrade head

# 6. Check status
docker-compose ps
curl http://localhost:8000/api/v1/health
```

### Digital Ocean App Platform (For Scaling)

- Deploy API as web service (auto-scaling)
- Deploy collectors as worker service
- Use managed TimescaleDB
- Automatic HTTPS and load balancing

## Monitoring

### Logs
- Structured JSON logs (stdout)
- Fields: timestamp, level, logger, message, listing_id, exchange, symbol
- Separate logs per collector instance

### Health Checks
- Collector heartbeat every 30s
- Data freshness monitoring (alert if no updates > 5 min)
- Database connection checks
- Gap detection (missing candles)

### Metrics (Future)
- Prometheus-compatible metrics endpoint
- Collector uptime, reconnection count
- API request rate and latency
- Database lag and table sizes

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py

# Run integration tests (requires DB)
pytest tests/integration/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Add your license here]

## Roadmap

### Near-Term
- [ ] Complete Phase 2-6 implementation
- [ ] Add Binance and Coinbase integrations
- [ ] Implement WebSocket streaming API
- [ ] Add Prometheus metrics

### Future
- [ ] Admin UI for listing management
- [ ] Additional data types (liquidations, orderbook depth)
- [ ] Continuous aggregates (pre-computed hourly/daily candles)
- [ ] Multi-region deployment
- [ ] GraphQL API (optional)

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

Built with ❤️ using Python, FastAPI, TimescaleDB, and CCXT
