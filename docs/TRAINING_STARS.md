# Training Stars - ML/Backtesting Data System

> **Training Stars** is a modular system for collecting historical cryptocurrency data from multiple exchanges (Binance, Bybit, OKX, etc.) for machine learning training and backtesting purposes.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Scripts](#scripts)
- [Usage Examples](#usage-examples)
- [Integration with Production](#integration-with-production)
- [FAQ](#faq)

---

## Overview

###  Why Training Stars?

**Problem**: Hyperliquid API only provides limited historical data:
- 1m candles: ~3-4 days
- 15m candles: ~52 days
- 4h/1d candles: ~365 days

**Solution**: Collect historical data from exchanges with extensive history (Binance, Bybit, etc.) for training ML models and backtesting strategies.

### Architecture Separation

```
┌─────────────────────────────────────────┐
│  PRODUCTION SYSTEM                      │
│  Database: kirby                        │
│  Config: starlistings.yaml              │
│  Exchange: Hyperliquid (real-time)      │
│  Purpose: Live trading data             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  TRAINING SYSTEM                        │
│  Database: kirby_training               │
│  Config: training_stars.yaml            │
│  Exchanges: Binance, Bybit, OKX, etc.   │
│  Purpose: ML training & backtesting     │
└─────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ Separate databases = no mixing production with training data
- ✅ Modular = easy to add/remove exchanges
- ✅ Flexible = different coins/intervals for training vs production
- ✅ Safe = training backfills don't affect live collectors

---

## Architecture

### Database Schema

The training database (`kirby_training`) has the same schema as production but stores data from multiple exchanges:

**Tables:**
- `exchanges` - Binance, Bybit, OKX, etc.
- `coins` - BTC, ETH, SOL, etc.
- `quote_currencies` - USDT, BUSD, etc.
- `market_types` - perps, spot
- `intervals` - 1m, 5m, 15m, 1h, 4h, 1d
- `starlistings` - Combinations to collect (same schema as realtime database)
- `candles` - Historical OHLCV data (TimescaleDB hypertable)

**Terminology Note**: Training stars are stored in the `starlistings` table within the `kirby_training` database. The term "training star" refers to the **purpose** (ML/backtesting data), while "starlisting" refers to the **database structure** (shared schema with realtime database). Both the realtime database (`kirby`) and training database (`kirby_training`) use the same `starlistings` table schema, but they're physically separate databases.

### Data Collection Flow

```
Config (training_stars.yaml)
    ↓
sync_training_config.py (writes to kirby_training DB)
    ↓
backfill_training.py (fetches historical data via CCXT)
    ↓
TimescaleDB (kirby_training.candles table)
    ↓
Export scripts → ML training / backtesting
```

---

## Quick Start

### 1. Create Training Database

```bash
# Connect to PostgreSQL
docker compose exec timescaledb psql -U kirby -d postgres

# Create training database
CREATE DATABASE kirby_training;

# Connect to training database
\c kirby_training

# Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

# Exit
\q
```

### 2. Run Migrations

```bash
# Run migrations on training database
docker compose exec collector env DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby_training alembic upgrade head
```

### 3. Configure Training Stars

Edit `config/training_stars.yaml` (already created with Binance defaults):

```yaml
training_stars:
  - exchange: binance
    coin: BTC
    quote: USDT
    market_type: perps
    intervals: [1m, 5m, 15m, 1h, 4h, 1d]
    active: true
```

### 4. Sync Configuration

```bash
# Sync training_stars.yaml to database
docker compose exec collector python -m scripts.sync_training_config
```

### 5. Backfill Historical Data

```bash
# Backfill 365 days of all active training stars
docker compose exec collector python -m scripts.backfill_training --days=365

# Or backfill specific exchange/coin
docker compose exec collector python -m scripts.backfill_training --exchange=binance --coin=BTC --days=365
```

---

## Configuration

### training_stars.yaml Structure

```yaml
# Exchanges
exchanges:
  - name: binance
    display_name: Binance
    active: true

# Coins
coins:
  - symbol: BTC
    name: Bitcoin
    active: true

# Quote Currencies
quote_currencies:
  - symbol: USDT
    name: Tether USD
    active: true

# Market Types
market_types:
  - name: perps
    display_name: Perpetual Futures
    active: true

# Intervals
intervals:
  - name: 1m
    seconds: 60
    active: true

# Training Stars (combinations to collect)
training_stars:
  - exchange: binance
    coin: BTC
    quote: USDT
    market_type: perps
    intervals: [1m, 5m, 15m, 1h, 4h, 1d]
    active: true
    notes: "Primary BTC training data"
```

### Environment Variables

Add to your `.env` file:

```bash
# Training Database
TRAINING_DB=kirby_training
TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby_training
TRAINING_DATABASE_POOL_SIZE=10
```

---

## Database Setup

### Option 1: Manual Setup (Docker)

```bash
# 1. Create database
docker compose exec timescaledb psql -U kirby -d postgres -c "CREATE DATABASE kirby_training;"

# 2. Enable TimescaleDB
docker compose exec timescaledb psql -U kirby -d kirby_training -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 3. Run migrations
docker compose exec collector env DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby_training alembic upgrade head

# 4. Verify
docker compose exec timescaledb psql -U kirby -d kirby_training -c "\dt"
```

### Option 2: Automated Script

```bash
# Run the setup script (creates DB + runs migrations)
docker compose exec collector python -m scripts.setup_training_db
```

---

## Scripts

### sync_training_config.py

Syncs `training_stars.yaml` configuration to the `kirby_training` database.

**Usage:**
```bash
docker compose exec collector python -m scripts.sync_training_config
```

**What it does:**
1. Reads `config/training_stars.yaml`
2. Creates/updates exchanges, coins, intervals, etc.
3. Creates training_stars records
4. Idempotent (safe to run multiple times)

### backfill_training.py

Backfills historical candle data from configured exchanges.

**Usage:**
```bash
# Backfill all active training stars (365 days)
docker compose exec collector python -m scripts.backfill_training --days=365

# Backfill specific exchange
docker compose exec collector python -m scripts.backfill_training --exchange=binance --days=365

# Backfill specific coin
docker compose exec collector python -m scripts.backfill_training --coin=BTC --days=180

# Backfill specific exchange + coin
docker compose exec collector python -m scripts.backfill_training --exchange=binance --coin=BTC --days=90
```

**Features:**
- Uses CCXT for multiple exchange support
- Automatic rate limiting
- Bulk upserts (500 candles/batch)
- Progress logging
- Error handling with retries

---

## Usage Examples

### Example 1: Backfill Binance BTC Data (1 Year)

```bash
# 1. Edit config/training_stars.yaml - ensure BTC is active
# 2. Sync config
docker compose exec collector python -m scripts.sync_training_config

# 3. Backfill 1 year of data
docker compose exec collector python -m scripts.backfill_training --exchange=binance --coin=BTC --days=365

# 4. Verify data
docker compose exec timescaledb psql -U kirby -d kirby_training -c "
SELECT
    i.name as interval,
    COUNT(*) as candles,
    MIN(c.time) as oldest,
    MAX(c.time) as newest
FROM candles c
JOIN starlistings s ON c.starlisting_id = s.id
JOIN intervals i ON s.interval_id = i.id
JOIN coins co ON s.coin_id = co.id
WHERE co.symbol = 'BTC'
GROUP BY i.name
ORDER BY i.name;
"
```

### Example 2: Add Multiple Exchanges

Edit `config/training_stars.yaml`:

```yaml
exchanges:
  - name: binance
    display_name: Binance
    active: true
  - name: bybit
    display_name: Bybit
    active: true

training_stars:
  - exchange: binance
    coin: BTC
    quote: USDT
    market_type: perps
    intervals: [1m, 15m, 1h, 4h]
    active: true

  - exchange: bybit
    coin: BTC
    quote: USDT
    market_type: perps
    intervals: [1m, 15m, 1h, 4h]
    active: true
```

Then sync and backfill:

```bash
docker compose exec collector python -m scripts.sync_training_config
docker compose exec collector python -m scripts.backfill_training --days=365
```

### Example 3: Export Training Data for ML

```bash
# Export merged Binance BTC data (all intervals)
docker compose exec collector python -m scripts.export_all \
  --database=training \
  --exchange=binance \
  --coin=BTC \
  --intervals=all \
  --days=365 \
  --format=parquet
```

---

## Integration with Production

### Data Flow Overview

```
┌─────────────────┐     ┌──────────────────┐
│  Production DB  │     │  Training DB     │
│  (kirby)        │     │  (kirby_training)│
├─────────────────┤     ├──────────────────┤
│ Hyperliquid     │     │ Binance, Bybit   │
│ Real-time data  │     │ Historical data  │
│ Live trading    │     │ ML training      │
└─────────────────┘     └──────────────────┘
         ↓                       ↓
    ┌─────────────────────────────────┐
    │     ML/Backtesting Pipeline     │
    │  - Train models on Binance data │
    │  - Test on Hyperliquid data     │
    │  - Deploy to live trading       │
    └─────────────────────────────────┘
```

### Typical Workflow

1. **Train ML Model**:
   - Use Binance 1m data (1+ years) from `kirby_training`
   - High-quality, liquid market data
   - Export via `export_all` script

2. **Backtest Strategy**:
   - Test on Binance data first
   - Then test on Hyperliquid historical data (if available)
   - Validate performance differences

3. **Live Trading**:
   - Deploy to Hyperliquid (production database)
   - Monitor real-time performance
   - Continue collecting training data

---

## FAQ

### Why separate databases?

**Isolation**: Training data is historical and static; production data is real-time and dynamic. Separating them prevents accidental mixing and makes data management clearer.

### Can I use the same database?

Yes, but not recommended. If you must, use a separate schema (`training` schema vs `public` schema) or prefixed tables (`training_candles` vs `candles`).

### Which exchanges should I use for training?

**Recommended**:
- **Binance**: Highest liquidity, most historical data, best for BTC/ETH
- **Bybit**: Good for altcoins, competitive liquidity
- **OKX**: Alternative to Binance, good coverage

**Avoid**: Low-liquidity exchanges with unreliable data.

### How much storage will this use?

**Estimates** (1m candles, 1 year, single coin):
- CSV: ~200 MB/year
- Parquet: ~20 MB/year (10x compression)
- Database: ~50 MB/year (with indexes)

**For training_stars.yaml defaults** (BTC+ETH+SOL, 6 intervals, 1 year):
- ~450 MB compressed
- ~2 GB in database with indexes

### Can I backfill older data incrementally?

Yes! The backfill script uses upserts, so you can:
- Run `--days=30` initially
- Later run `--days=365` to fill the gaps
- No duplicates, only missing data is added

### How often should I run backfills?

**Training data is static** - run once to get historical data, then you're done. Unlike production starlistings which collect real-time, training stars are for historical backfilling only.

**Exception**: If you want to continuously add recent data to training set, run weekly/monthly backfills.

### Performance impact on production?

**Minimal**: Training backfills use a separate database, so they don't affect:
- Production data collection
- API queries
- Disk I/O contention is minimal (different databases)

### Can I query both databases together?

Yes, using PostgreSQL's `dblink` extension or by connecting to both databases in your application code.

---

## Troubleshooting

### Database doesn't exist

```bash
# Create it
docker compose exec timescaledb psql -U kirby -d postgres -c "CREATE DATABASE kirby_training;"
```

### Tables don't exist

```bash
# Run migrations
docker compose exec collector env DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby_training alembic upgrade head
```

### Backfill fails with "exchange not supported"

Check that the exchange is supported by CCXT:
```python
import ccxt
print(ccxt.exchanges)  # List all supported exchanges
```

Ensure the exchange name in `training_stars.yaml` matches CCXT's name exactly.

### Rate limit errors

Increase the delay in backfill script or reduce batch size. CCXT has built-in rate limiting (`enableRateLimit: True`), but some exchanges are stricter.

---

## Next Steps

1. ✅ Create training database
2. ✅ Configure `training_stars.yaml`
3. ✅ Sync configuration
4. ✅ Backfill historical data (start with 30 days, then expand to 365)
5. ✅ Export data for ML pipeline
6. ✅ Train models
7. ✅ Backtest strategies
8. ✅ Deploy to production!

---

**Last Updated**: November 3, 2025
**Version**: 1.0.0 - Initial Release
