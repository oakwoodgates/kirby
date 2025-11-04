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

### 4. Backfill Training Data with NordVPN (Optional)

Once databases are set up, you can backfill historical data from Binance using NordVPN.

**Note**: The `deploy.sh` script automatically detects and configures the TimescaleDB IP for VPN networking. You don't need to configure this manually.

#### Step 4.1: Configure NordVPN

```bash
# Edit .env and add NordVPN token
nano .env

# Add these lines:
NORDVPN_TOKEN=your_actual_token_here
NORDVPN_COUNTRY=Chile
NORDVPN_TECHNOLOGY=NordLynx
```

#### Step 4.2: Start VPN

```bash
# Start VPN (only starts when explicitly requested)
docker compose --profile vpn up -d vpn

# Wait for connection
sleep 30

# Verify connection
docker compose logs vpn | tail -20

# Test Binance access
docker compose exec vpn curl -s https://api.binance.com/api/v3/ping
# Should return: {}
```

#### Step 4.3: Run Backfills (Through VPN)

```bash
# Backfill BTC data for the last 30 days
docker compose --profile vpn --profile tools run --rm collector-training python -m scripts.backfill_training --coin=BTC --days=30

# Backfill all configured coins
docker compose --profile vpn --profile tools run --rm collector-training python -m scripts.backfill_training --days=30

# Backfill specific exchange
docker compose --profile vpn --profile tools run --rm collector-training python -m scripts.backfill_training --exchange=binance --days=90
```

**Note**: Both `--profile vpn` and `--profile tools` are required to enable both the VPN and collector-training services.

#### Step 4.4: Stop VPN When Done

```bash
# Stop VPN to save resources
docker compose stop vpn
```

**Important Notes:**
- VPN **does NOT auto-start** - you manually start it when needed
- Use `docker compose run --rm collector-training` (NOT `docker compose exec collector`)
- This routes traffic through Chile VPN to access Binance
- Stop VPN when done to save CPU/memory
- For complete VPN setup, see [docs/NORDVPN_SETUP.md](docs/NORDVPN_SETUP.md)

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
