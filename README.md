# Kirby

> High-performance cryptocurrency market data ingestion and API platform

Kirby ingests real-time and historical market data from multiple cryptocurrency exchanges and serves it via a fast, reliable REST API. Named after the Nintendo character that can consume unlimited objects, Kirby efficiently handles massive volumes of market data.

---

## Features

- **Real-time Data Collection**: WebSocket connections for live OHLCV candle data
- **Historical Backfills**: Automated retrieval of historical market data
- **High Performance**: Async I/O with optimized bulk inserts using asyncpg
- **Time-Series Optimized**: TimescaleDB for efficient storage and querying
- **Modular Architecture**: Easy to add new exchanges, coins, and market types
- **Production Ready**: Health checks, monitoring, structured logging
- **Type-Safe**: Full Pydantic validation and type hints throughout
- **API-First**: FastAPI with auto-generated OpenAPI documentation

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Run with Docker

```bash
# Clone the repository
git clone <repository-url>
cd kirby

# Copy environment template
cp .env.example .env

# Start services
cd docker
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Sync configuration to database
docker-compose exec api python -m scripts.sync_config

# View logs
docker-compose logs -f
```

The API will be available at `http://localhost:8000`

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

```bash
# Backfill 1 year of data for all active starlistings
python -m scripts.backfill --days=365

# Backfill specific exchange and coin
python -m scripts.backfill --exchange=hyperliquid --coin=BTC --days=90

# Resume interrupted backfill
python -m scripts.backfill --resume
```

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

### Interactive API Documentation

Once the API is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

### Production Deployment

For production deployment on Digital Ocean or other platforms:

1. **Build production images:**

```bash
docker build -f docker/Dockerfile --target api -t kirby-api:latest .
docker build -f docker/Dockerfile --target collector -t kirby-collector:latest .
```

2. **Set environment variables:**

```bash
ENVIRONMENT=production
LOG_LEVEL=info
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/kirby
API_WORKERS=8
```

3. **Deploy with Docker Compose or Kubernetes**

4. **Run migrations:**

```bash
docker run --rm kirby-api:latest alembic upgrade head
```

5. **Monitor logs and health endpoints**

### Environment-Specific Settings

- **Development**: Auto-reload enabled, DEBUG logging, small pool sizes
- **Staging**: Production-like settings, INFO logging
- **Production**: Optimized pool sizes, JSON logging, monitoring enabled

---

## Monitoring

### Key Metrics

- **Data Freshness**: Time since last candle received
- **Collection Lag**: Delay between exchange and ingestion
- **API Latency**: Response time percentiles (P50, P95, P99)
- **Error Rates**: Failed requests, collector crashes
- **Throughput**: Candles/second, requests/second

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

### Current MVP (Phase 1-2)
- ✅ TimescaleDB schema with hypertables
- ✅ Configuration management (YAML → database)
- ✅ Database repositories and connection pooling
- 🚧 Hyperliquid WebSocket collector
- 🚧 Historical backfill system
- 🚧 REST API endpoints
- 🚧 Health checks and monitoring

### Future Phases
- WebSocket API for real-time streaming
- Additional exchanges (Binance, Coinbase, OKX)
- More data types (trades, order book, funding rates)
- Caching layer (Redis)
- Advanced monitoring (Prometheus, Grafana)
- Multi-region deployment

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
