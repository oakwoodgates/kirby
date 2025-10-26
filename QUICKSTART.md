# Kirby - Quick Start Guide

Get Kirby up and running in 5 minutes!

## Quick Deployment (Local or Server)

### Prerequisites
- Docker & Docker Compose installed
- Git installed

### One-Command Deploy

```bash
# Clone the repository
git clone https://github.com/oakwoodgates/kirby.git
cd kirby

# Run deployment script
chmod +x deploy.sh
./deploy.sh
```

That's it! The script will:
1. Generate secure credentials
2. Build Docker images
3. Start all services
4. Run database migrations
5. Configure starlistings

## Manual Deployment

If you prefer manual control:

```bash
# 1. Create environment file
cp .env.example .env
nano .env  # Edit POSTGRES_PASSWORD

# 2. Build and start
docker compose build
docker compose up -d

# 3. Run migrations
docker compose exec collector alembic upgrade head

# 4. Sync configuration
docker compose exec collector python scripts/sync_config.py

# 5. Check status
docker compose ps
docker compose logs -f
```

## Verify It's Working

```bash
# Check API health
curl http://localhost:8000/health

# View configured trading pairs
curl http://localhost:8000/api/v1/starlistings | jq

# Wait 1-2 minutes, then check collected data
curl http://localhost:8000/api/v1/candles?limit=5 | jq
```

## Common Commands

```bash
# View logs
docker compose logs -f              # All services
docker compose logs -f collector    # Just collector
docker compose logs -f api          # Just API

# Restart services
docker compose restart              # All services
docker compose restart collector    # Just collector

# Stop/Start
docker compose stop                 # Stop all
docker compose start                # Start all

# Check status
docker compose ps                   # Service status
docker stats                        # Resource usage

# Database access
docker compose exec timescaledb psql -U kirby -d kirby
```

## What's Collecting?

By default, Kirby collects:
- **BTC/USD** perpetuals: 1m, 15m, 4h, 1d candles
- **SOL/USD** perpetuals: 1m, 15m, 4h, 1d candles

From **Hyperliquid** exchange via WebSocket.

## Add More Coins

Edit `config/starlistings.yaml`:

```yaml
starlistings:
  - exchange: hyperliquid
    coin: ETH  # Add Ethereum
    quote: USD
    market_type: perps
    intervals:
      - 1m
      - 1h
```

Then sync:
```bash
docker compose exec collector python scripts/sync_config.py
docker compose restart collector
```

## Production Deployment (Digital Ocean)

For production deployment to Digital Ocean, see:
**[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with security hardening

## Troubleshooting

### Services won't start?
```bash
docker compose logs
docker system df  # Check disk space
```

### No data collecting?
```bash
docker compose logs collector
# Look for "Connected to Hyperliquid WebSocket"
```

### Can't connect to API?
```bash
curl http://localhost:8000/health
docker compose ps api
```

### Reset everything?
```bash
docker compose down -v
./deploy.sh
```

## Project Structure

```
kirby/
├── src/
│   ├── api/              # REST API endpoints
│   ├── collectors/       # Exchange data collectors
│   ├── db/              # Database models & repositories
│   ├── config/          # Configuration management
│   └── utils/           # Helper functions
├── config/
│   └── starlistings.yaml # Trading pair configuration
├── migrations/          # Database migrations
├── tests/              # Test suite
├── scripts/            # Utility scripts
├── docker-compose.yml  # Service orchestration
└── Dockerfile         # Application container
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/starlistings` - List trading pairs
- `GET /api/v1/candles` - Query candle data
  - `?starlisting_id=1` - Filter by trading pair
  - `?start_time=2025-10-26T00:00:00Z` - Filter by time
  - `?limit=100` - Limit results

Full API docs: http://localhost:8000/docs (when running)

## Next Steps

1. **Monitor**: Watch logs for 24 hours to ensure stability
2. **Backup**: Set up automated database backups
3. **Security**: Review [DEPLOYMENT.md](DEPLOYMENT.md) security section
4. **Scale**: Add more exchanges and trading pairs
5. **Analyze**: Build dashboards with your collected data

## Resources

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete production deployment guide
- [TESTING.md](TESTING.md) - Testing guide
- [README.md](README.md) - Full project documentation

## Support

Issues? Check:
1. `docker compose logs` for errors
2. [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
3. GitHub Issues: https://github.com/oakwoodgates/kirby/issues

---

**Happy Collecting!** 🚀
