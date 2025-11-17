# Kirby

> High-performance cryptocurrency market data ingestion and API platform

Kirby ingests real-time and historical market data from multiple cryptocurrency exchanges and serves it via a fast, reliable REST API. Named after the Nintendo character that can consume unlimited objects, Kirby efficiently handles massive volumes of market data.

---

## Features

- **Real-time Data Collection**: WebSocket connections for live OHLCV candles, funding rates, and open interest
- **1-Minute Buffering**: Optimized storage for funding/OI data (98.3% storage reduction)
- **Historical Backfills**: Automated retrieval of historical candle and funding rate data
- **High Performance**: Async I/O with optimized bulk inserts using asyncpg
- **Time-Series Optimized**: TimescaleDB with minute-precision timestamps aligned across all data types
- **Modular Architecture**: Easy to add new exchanges, coins, and market types
- **Production Ready**: Health checks, monitoring, structured logging, Docker deployment
- **Type-Safe**: Full Pydantic validation and type hints throughout
- **API-First**: FastAPI with auto-generated OpenAPI documentation

---

## Quick Start

### 🚀 Get Started in 5 Minutes

```bash
git clone https://github.com/oakwoodgates/kirby.git
cd kirby
./deploy.sh
```

That's it! See **[QUICKSTART.md](QUICKSTART.md)** for details.

### 📦 Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for local development)

### 🐳 Docker Deployment

```bash
# Clone the repository
git clone https://github.com/oakwoodgates/kirby.git
cd kirby

# Copy and configure environment
cp .env.example .env
nano .env  # Edit POSTGRES_PASSWORD

# Build and start all services
docker compose build
docker compose up -d

# Run database migrations
docker compose exec collector alembic upgrade head

# Sync configuration to database
docker compose exec collector python -m scripts.sync_config

# Check status
docker compose ps
docker compose logs -f
```

The API will be available at `http://localhost:8000`

### 📚 Deployment Guides

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute quick start guide
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete Digital Ocean deployment guide
  - Server setup and security hardening
  - Production configuration
  - Monitoring and maintenance
  - Backup strategies
  - Troubleshooting guide

---

## Installation

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Start TimescaleDB (via Docker or local installation)
docker-compose up -d timescaledb

# Run migrations
alembic upgrade head

# Sync configuration
python -m scripts.sync_config
```

### Database Setup

Kirby uses TimescaleDB (PostgreSQL with time-series extension). The Docker Compose setup includes TimescaleDB, but for local PostgreSQL:

```bash
# Install TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

# Run migrations
alembic upgrade head
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://kirby:password@localhost:5432/kirby
DATABASE_POOL_SIZE=20

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Logging
ENVIRONMENT=development
LOG_LEVEL=info
LOG_FORMAT=json

# Collectors
COLLECTOR_RESTART_DELAY=5
COLLECTOR_MAX_RETRIES=3
COLLECTOR_BACKFILL_ON_GAP=true
```

See [.env.example](.env.example) for all available options.

### Starlisting Configuration

Define what data to collect in `config/starlistings.yaml`:

```yaml
exchanges:
  - name: hyperliquid
    display_name: Hyperliquid
    active: true

coins:
  - symbol: BTC
    name: Bitcoin
    active: true

market_types:
  - name: perps
    display_name: Perpetuals
    active: true

starlistings:
  - exchange: hyperliquid
    coin: BTC
    market_type: perps
    intervals:
      - 1m
      - 15m
      - 4h
      - 1d
    active: true
```

After editing, sync to database:

```bash
python -m scripts.sync_config
```

---

## Usage

### Starting the Services

```bash
# Start all services (database, API, collector)
docker-compose up -d

# Start only specific services
docker-compose up -d timescaledb api

# View logs
docker-compose logs -f api
docker-compose logs -f collector
```

### Backfilling Historical Data

**Important**: All backfill commands must run **inside the Docker container** using `docker compose exec collector`.

#### Backfill Candles

```bash
# Backfill all active starlistings (1 year)
docker compose exec collector python -m scripts.backfill --days=365

# Backfill specific exchange and coin
docker compose exec collector python -m scripts.backfill --exchange=hyperliquid --coin=BTC --days=90

# Backfill specific coin (all intervals)
docker compose exec collector python -m scripts.backfill --coin=SOL --days=30
```

#### Backfill Funding Rates

```bash
# Backfill all active coins (1 year)
docker compose exec collector python -m scripts.backfill_funding --days=365

# Backfill specific coin (BTC, 30 days)
docker compose exec collector python -m scripts.backfill_funding --coin=BTC --days=30

# Backfill using --all flag
docker compose exec collector python -m scripts.backfill_funding --all
```

**Hyperliquid API Limitations**:
- Historical funding data only includes `funding_rate` and `premium`
- No historical data for: `mark_price`, `oracle_price`, `mid_price`, `open_interest`
- Real-time collector captures ALL fields going forward
- Backfill uses COALESCE to preserve existing complete data (safe to re-run)

### Health Checks

```bash
# Manual health check
python -m scripts.health_check

# Or via API
curl http://localhost:8000/health
curl http://localhost:8000/health/hyperliquid
```

---

## API Documentation

### Base URL

```
http://localhost:8000
```

### Endpoints

#### Get Candle Data

```http
GET /candles/{exchange}/{coin}/{quote}/{market_type}/{interval}
```

**Parameters:**
- `exchange` - Exchange name (e.g., `hyperliquid`)
- `coin` - Base coin symbol (e.g., `BTC`)
- `quote` - Quote currency symbol (e.g., `USD`)
- `market_type` - Market type (e.g., `perps`)
- `interval` - Time interval (e.g., `15m`, `4h`, `1d`)

**Query Parameters:**
- `start_time` (optional) - Start time (ISO 8601 or Unix timestamp)
- `end_time` (optional) - End time (ISO 8601 or Unix timestamp)
- `limit` (optional) - Maximum number of candles (default: 1000, max: 5000)

**Example:**
```bash
curl "http://localhost:8000/candles/hyperliquid/BTC/USD/perps/15m?limit=100"
```

**Response:**
```json
{
  "data": [
    {
      "time": "2025-10-26T12:00:00Z",
      "open": "67500.50",
      "high": "67800.00",
      "low": "67400.25",
      "close": "67650.75",
      "volume": "1234.5678",
      "num_trades": 542
    }
  ],
  "metadata": {
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "interval": "15m",
    "count": 100
  }
}
```

#### List Starlistings

```http
GET /starlistings
```

**Example:**
```bash
curl http://localhost:8000/starlistings
```

**Response:**
```json
{
  "starlistings": [
    {
      "id": 1,
      "exchange": "hyperliquid",
      "exchange_display": "Hyperliquid",
      "coin": "BTC",
      "coin_name": "Bitcoin",
      "quote": "USD",
      "quote_name": "US Dollar",
      "trading_pair": "BTC/USD",
      "market_type": "perps",
      "market_type_display": "Perpetuals",
      "interval": "15m",
      "interval_seconds": 900,
      "active": true
    }
  ],
  "total_count": 1
}
```

#### Health Check

```http
GET /health
GET /health/{exchange}
```

**Example:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T12:00:00Z",
  "database": "connected",
  "collectors": {
    "hyperliquid": "running"
  }
}
```

#### Get Funding Rates

```http
GET /funding/{exchange}/{coin}/{quote}/{market_type}
```

**Parameters:**
- `exchange` - Exchange name (e.g., `hyperliquid`)
- `coin` - Base coin symbol (e.g., `BTC`)
- `quote` - Quote currency symbol (e.g., `USD`)
- `market_type` - Market type (e.g., `perps`)

**Query Parameters:**
- `start_time` (optional) - Start time (ISO 8601 or Unix timestamp)
- `end_time` (optional) - End time (ISO 8601 or Unix timestamp)
- `limit` (optional) - Maximum number of records (default: 1000, max: 5000)

**Example:**
```bash
curl "http://localhost:8000/funding/hyperliquid/BTC/USD/perps?limit=10"
```

**Response:**
```json
{
  "data": [
    {
      "time": "2025-10-26T12:00:00+00:00",
      "funding_rate": "0.0001000000",
      "premium": "0.0000500000",
      "mark_price": "67500.50",
      "index_price": "67495.00",
      "oracle_price": "67495.00",
      "mid_price": "67500.00",
      "next_funding_time": "2025-10-26T13:00:00+00:00"
    }
  ],
  "metadata": {
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "count": 10
  }
}
```

#### Get Open Interest

```http
GET /open-interest/{exchange}/{coin}/{quote}/{market_type}
```

**Parameters:**
- `exchange` - Exchange name (e.g., `hyperliquid`)
- `coin` - Base coin symbol (e.g., `BTC`)
- `quote` - Quote currency symbol (e.g., `USD`)
- `market_type` - Market type (e.g., `perps`)

**Query Parameters:**
- `start_time` (optional) - Start time (ISO 8601 or Unix timestamp)
- `end_time` (optional) - End time (ISO 8601 or Unix timestamp)
- `limit` (optional) - Maximum number of records (default: 1000, max: 5000)

**Example:**
```bash
curl "http://localhost:8000/open-interest/hyperliquid/BTC/USD/perps?limit=10"
```

**Response:**
```json
{
  "data": [
    {
      "time": "2025-10-26T12:00:00+00:00",
      "open_interest": "12345.67890000",
      "notional_value": "833333333.5000",
      "day_base_volume": "98765.43210000",
      "day_notional_volume": "6666666666.0000"
    }
  ],
  "metadata": {
    "exchange": "hyperliquid",
    "coin": "BTC",
    "quote": "USD",
    "trading_pair": "BTC/USD",
    "market_type": "perps",
    "count": 10
  }
}
```

### Interactive API Documentation

Once the API is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### WebSocket API (Real-time Streaming)

Kirby provides a WebSocket API for real-time candle data streaming.

#### Connection

```
ws://localhost:8000/ws
```

#### Quick Example

**Python:**
```python
import asyncio
import json
import websockets

async def stream_candles():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        # Subscribe to BTC/USD 1m candles
        subscribe_msg = {
            "action": "subscribe",
            "starlisting_ids": [1],
            "history": 10  # Get 10 historical candles
        }
        await ws.send(json.dumps(subscribe_msg))

        # Receive real-time updates
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "candle":
                print(f"New candle: {data['data']}")

asyncio.run(stream_candles())
```

**JavaScript:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "candle") {
        console.log("New candle:", data.data);
    }
};

// Subscribe to multiple starlistings
ws.send(JSON.stringify({
    action: "subscribe",
    starlisting_ids: [1, 2, 3],
    history: 10
}));
```

#### Features

- ✅ **Real-time updates** (~50-100ms latency via PostgreSQL LISTEN/NOTIFY)
- ✅ **Subscribe to multiple starlistings** simultaneously
- ✅ **Historical data on connect** (optional, up to 1000 candles)
- ✅ **Heartbeat/ping** for connection health
- ✅ **Auto-reconnection** support
- ✅ **Validated messages** with error responses

#### Complete Documentation

See **[docs/WEBSOCKET_API.md](docs/WEBSOCKET_API.md)** for complete WebSocket API documentation including:
- Message protocol specification
- Client examples (Python & JavaScript)
- Error handling and reconnection strategies
- Performance considerations
- Troubleshooting guide

#### Test Clients

**Python Test Client:**
```bash
python scripts/test_websocket_client.py
```

**JavaScript Test Client:**
```bash
# Open in browser
open docs/examples/websocket_client.html
```

---

## Data Export

Kirby provides powerful export capabilities for AI/ML training, backtesting, and external analysis.

### Export Scripts

Four CLI scripts are available for exporting data in CSV and Parquet formats:

1. **export_candles.py** - OHLCV candle data with multi-interval support
2. **export_funding.py** - Funding rate data with price context
3. **export_oi.py** - Open interest data with volume metrics
4. **export_all.py** - Merged datasets (candles + funding + OI) for ML/backtesting

### Quick Examples

```bash
# Export BTC 1m candles for last 30 days (both CSV and Parquet)
docker compose exec collector python -m scripts.export_candles \
  --coin BTC --intervals 1m --days 30

# Export merged dataset for ML training (Parquet only)
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals 1m --days 90 --format parquet

# Export all intervals for multi-timeframe backtesting
docker compose exec collector python -m scripts.export_all \
  --coin BTC --intervals all --days 365

# Export funding rates only
docker compose exec collector python -m scripts.export_funding \
  --coin BTC --days 30
```

### File Formats

- **CSV**: Universal format, human-readable, larger file size
- **Parquet**: Columnar format, ~10x smaller, optimized for pandas/PyTorch/TensorFlow

### Merged Datasets

The `export_all.py` script creates ML-ready datasets by merging:
- Candle data (OHLCV)
- Funding rates (with mark/index/oracle prices)
- Open interest (with volume metrics)

All data is aligned by minute-precision timestamps. Missing values are preserved as NULL (no forward-filling).

### Output Location

Exports are saved to the `exports/` directory with timestamped filenames:

```
exports/
├── merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.parquet
├── merged_hyperliquid_BTC_USD_perps_1m_20251102_143022.json
└── ... (metadata files)
```

### Complete Documentation

For comprehensive export documentation including:
- Advanced usage examples
- Integration with ML frameworks (PyTorch, TensorFlow, scikit-learn)
- Best practices and troubleshooting
- Format comparison and optimization tips

See **[docs/EXPORT.md](docs/EXPORT.md)**

---

## Development

### Project Structure

```
kirby/
├── src/
│   ├── api/              # FastAPI application
│   ├── collectors/       # Data collectors
│   ├── db/               # Database models and repositories
│   ├── schemas/          # Pydantic schemas
│   ├── config/           # Configuration management
│   └── utils/            # Utilities
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── scripts/              # Operational scripts
├── config/               # Configuration files
├── migrations/           # Database migrations
└── docker/               # Docker configuration
```

### Adding a New Exchange

1. **Create collector class** in `src/collectors/{exchange_name}.py`:

```python
from src.collectors.base import BaseCollector

class NewExchangeCollector(BaseCollector):
    async def connect(self):
        # Implement WebSocket connection
        pass

    async def collect(self):
        # Implement data collection
        pass
```

2. **Update configuration** in `config/starlistings.yaml`

3. **Register collector** in `src/collectors/main.py`

4. **Test and backfill**

### Code Quality

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy src

# Run all checks
black . && ruff check . && mypy src
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Testing

### Setup Testing Environment

First-time setup:

```bash
# Windows
scripts\setup_dev.bat

# Mac/Linux
bash scripts/setup_dev.sh
```

This will:
- Create a Python virtual environment
- Install Kirby with dev dependencies
- Prepare your environment for testing

### Run Tests

```bash
# Easy way - automatically sets up test database
python scripts/run_tests.py

# Or run pytest directly
pytest

# Unit tests only
pytest tests/unit -m unit

# Integration tests only
pytest tests/integration -m integration

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_helpers.py

# Verbose output
pytest -v
```

### Test Coverage

The test suite includes:
- **Unit tests**: Helper functions, utilities, data validation
- **Integration tests**: API endpoints, database operations, repositories
- **Coverage reporting**: HTML and terminal reports

For detailed testing documentation, see [TESTING.md](TESTING.md).

### Test Database

Integration tests automatically create and use a separate test database (`kirby_test`). No manual configuration needed!

---

## Deployment

### 🌐 Production Deployment to Digital Ocean

Complete step-by-step guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

**Quick Deploy:**
```bash
# On your Digital Ocean droplet:
git clone https://github.com/oakwoodgates/kirby.git
cd kirby
./deploy.sh
```

The deployment guide includes:
1. ☁️ Digital Ocean Droplet setup ($12-24/month)
2. 🔒 Server configuration and security hardening
3. 🐳 Docker installation and configuration
4. 🚀 One-command or manual deployment options
5. 📊 Monitoring and maintenance procedures
6. 🔐 Security: UFW firewall, fail2ban, SSH hardening
7. 💾 Automated backup strategies
8. 🔧 Comprehensive troubleshooting guide

### Environment-Specific Settings

```bash
# Development
ENVIRONMENT=development
LOG_LEVEL=debug
DATABASE_POOL_SIZE=10

# Production
ENVIRONMENT=production
LOG_LEVEL=info
DATABASE_POOL_SIZE=20
```

### Production Checklist

Before going live:
- [ ] Changed default PostgreSQL password
- [ ] Configured firewall (UFW)
- [ ] Set up SSL/TLS for API (if public-facing)
- [ ] Configured log rotation
- [ ] Set up automated backups
- [ ] Enabled fail2ban
- [ ] Monitored services for 24 hours
- [ ] Set up alerting (optional: Grafana, Prometheus)

See full checklist in [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Monitoring

### Key Metrics

- **Data Freshness**: Time since last candle/funding/OI received
- **Collection Lag**: Delay between exchange and ingestion
- **API Latency**: Response time percentiles (P50, P95, P99)
- **Error Rates**: Failed requests, collector crashes
- **Throughput**: Candles/second, requests/second
- **Buffer Flush**: Check logs for "Flushed buffers to database" every minute

### Logging

Structured JSON logs in production:

```json
{
  "timestamp": "2025-10-26T12:00:00Z",
  "level": "INFO",
  "logger": "kirby.collector.hyperliquid",
  "message": "Collected 120 candles",
  "extra": {
    "exchange": "hyperliquid",
    "candles": 120,
    "duration_ms": 45
  }
}
```

---

## Troubleshooting

### Common Issues

**Database connection errors:**
- Verify `DATABASE_URL` is correct
- Ensure TimescaleDB is running: `docker-compose ps`
- Check database logs: `docker-compose logs timescaledb`

**Collector not receiving data:**
- Check exchange API status
- Verify WebSocket connection: `docker-compose logs collector`
- Check rate limiting settings

**Missing data gaps:**
- Run gap detection: `python -m scripts.detect_gaps`
- Trigger backfill: `python -m scripts.backfill --fill-gaps`

**API slow response:**
- Check database query performance
- Verify indexes are created: `alembic current`
- Increase `DATABASE_POOL_SIZE` in `.env`

### Debug Mode

Enable debug logging:

```bash
# In .env
LOG_LEVEL=debug
API_LOG_LEVEL=debug

# Restart services
docker-compose restart
```

---

## Roadmap

### ✅ Completed Features
- ✅ TimescaleDB schema with hypertables
- ✅ Configuration management (YAML → database)
- ✅ Database repositories and connection pooling
- ✅ Hyperliquid WebSocket collector (candles)
- ✅ Hyperliquid WebSocket collector (funding/OI with 1-minute buffering)
- ✅ Historical backfill system (candles + funding rates)
- ✅ REST API endpoints (candles, funding, OI, starlistings, health)
- ✅ Health checks and monitoring
- ✅ Docker deployment with production guide
- ✅ 1-minute buffering for funding/OI (98.3% storage reduction)
- ✅ COALESCE pattern for safe backfills
- ✅ Minute-precision timestamp alignment across all tables

### 🚧 In Progress
- WebSocket API for real-time streaming (with Redis for sub-minute data)
- Advanced monitoring (Prometheus, Grafana)

### 🔮 Future Phases
- Additional exchanges (Binance, Coinbase, OKX)
- More data types (trades, order book, liquidations)
- Caching layer (Redis for real-time serving)
- Multi-region deployment
- Rate limiting and authentication
- Automated data retention policies

---

## Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Write tests** for new functionality
4. **Follow code style**: Run `black` and `ruff`
5. **Update documentation** as needed
6. **Commit changes**: `git commit -m 'Add amazing feature'`
7. **Push to branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

### Code Standards

- Type hints for all functions
- Pydantic validation for external data
- Async/await for I/O operations
- Comprehensive error handling
- Unit and integration tests
- Docstrings for public APIs

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **FastAPI**: Modern, fast web framework
- **TimescaleDB**: Time-series database built on PostgreSQL
- **CCXT**: Cryptocurrency exchange trading library
- **Hyperliquid**: Exchange API and SDK

---

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review existing documentation in [CLAUDE.md](CLAUDE.md)
- Check API docs at http://localhost:8000/docs

---

**Built with ⚡ by Oakwood Gates**
