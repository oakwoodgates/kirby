# Training Database Deployment Guide

## Quick Setup on Digital Ocean

If you've already deployed Kirby but don't have the training database set up yet, follow these steps:

### 1. Pull Latest Changes

```bash
cd ~/kirby
git pull origin main
```

### 2. Run Automated Deployment

The `deploy.sh` script now handles BOTH databases automatically:

```bash
./deploy.sh
```

This will:
- ✅ Set up production database (kirby) - 8 starlistings
- ✅ Set up training database (kirby_training) - 24 starlistings
- ✅ Run all migrations
- ✅ Sync all configurations
- ✅ Verify both databases

### 3. Verify Deployment

```bash
# Check production database
docker compose exec timescaledb psql -U kirby -d kirby -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 8 starlistings

# Check training database
docker compose exec timescaledb psql -U kirby -d kirby_training -c "SELECT COUNT(*) FROM starlistings;"
# Expected: 24 starlistings

# Or use the verification script
docker compose exec collector python -m scripts.verify_deployment
```

### 4. Backfill Training Data (Optional)

Once databases are set up, you can backfill historical data from Binance:

```bash
# Backfill BTC data for the last 7 days
docker compose exec collector python -m scripts.backfill_training --coin=BTC --days=7

# Backfill all configured coins
docker compose exec collector python -m scripts.backfill_training --days=7

# Backfill specific exchange
docker compose exec collector python -m scripts.backfill_training --exchange=binance --days=30
```

**Note**: Binance may geo-restrict access. If you see 451 errors, you'll need a VPN on your server.

---

## What Changed

### Files Modified

1. **[deploy.sh](deploy.sh)** - Now automatically sets up both databases
2. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Updated with automated deployment instructions
3. **[.env.example](.env.example)** - Fixed to use `timescaledb` as default host
4. **[scripts/verify_deployment.py](scripts/verify_deployment.py)** - New verification script

### Key Fixes

- ✅ Training database is now created automatically
- ✅ Migrations run on both databases
- ✅ Configuration is synced for both databases
- ✅ Environment variables properly overridden in Docker
- ✅ Database URLs use correct Docker service name

### Database Architecture

```
Production Database (kirby):
  - Real-time Hyperliquid data collection
  - 8 starlistings: BTC, SOL × perps × 4 intervals (1m, 15m, 4h, 1d)
  - Used by API endpoints

Training Database (kirby_training):
  - Historical data from multiple exchanges (Binance, Bybit, etc.)
  - 24 starlistings: BTC, ETH, SOL × perps/spot × 6 intervals
  - Used for ML training and backtesting
```

---

## Troubleshooting

### "localhost" Connection Errors

If you see errors about connecting to localhost:5432, it means your `.env` file has the wrong host. Update it:

```bash
# Edit .env
nano .env

# Change:
DATABASE_URL=postgresql+asyncpg://kirby:PASSWORD@localhost:5432/kirby
TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:PASSWORD@localhost:5432/kirby_training

# To:
DATABASE_URL=postgresql+asyncpg://kirby:PASSWORD@timescaledb:5432/kirby
TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:PASSWORD@timescaledb:5432/kirby_training
```

Then restart services:
```bash
docker compose restart collector api
```

### Training Database Missing

If training database doesn't exist, the deploy script creates it automatically. Just run:

```bash
./deploy.sh
```

### Verify Everything is Working

```bash
# Run comprehensive verification
docker compose exec collector python -m scripts.verify_deployment

# Check logs
docker compose logs -f collector

# Check API
curl http://localhost:8000/health
```

---

## For Future Updates

Whenever you update Kirby:

```bash
cd ~/kirby
git pull origin main
./deploy.sh
```

The script is **idempotent** - safe to run multiple times, handles both fresh deployments and updates.
