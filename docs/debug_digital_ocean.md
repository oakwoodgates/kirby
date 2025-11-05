# Debug Binance num_trades on Digital Ocean

## Step 1: SSH to your server and pull latest code

```bash
# SSH to Digital Ocean
ssh your-user@your-server-ip

# Navigate to project
cd /path/to/kirby

# Pull latest code (includes commit 999794a with Binance raw API)
git pull origin main

# Check that you have the Binance commit
git log --oneline -3
# Should show: 999794a get data direct from binance; fix num_trades
```

## Step 2: Rebuild Docker images with new code

```bash
# Rebuild collector image (includes python-binance dependency)
docker compose build collector

# Or rebuild all services
docker compose build

# Verify python-binance is installed
docker compose exec collector python -c "import binance; print(f'python-binance version: {binance.__version__}')"
# Should output: python-binance version: 1.0.XX
```

## Step 3: Check VPN is running

```bash
# Start VPN if not running
docker compose up -d vpn

# Wait 30 seconds for connection
sleep 30

# Verify VPN connected
docker compose logs vpn | grep "You are connected"
# Should show: You are connected to Chile #XX
```

## Step 4: Run backfill with debug output

```bash
# Small test: BTC only, 1 hour of data
docker compose --profile vpn --profile tools run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=0.042 2>&1 | tee backfill_debug.log

# Look for these debug messages in output:
# >>> BINANCE BRANCH EXECUTING <<<
# >>> First candle has 12 fields
# >>> num_trades (field 8) = XXXX
# >>> All have num_trades: True
```

## Step 5: Verify in database

```bash
# Check if num_trades is populated
docker compose exec timescaledb psql -U kirby -d kirby_training -c "
  SELECT
    time,
    num_trades,
    volume,
    open,
    close
  FROM candles c
  JOIN starlistings s ON c.starlisting_id = s.id
  JOIN coins co ON s.coin_id = co.id
  WHERE co.symbol = 'BTC'
    AND num_trades IS NOT NULL
  ORDER BY time DESC
  LIMIT 10;
"

# Count how many candles have num_trades
docker compose exec timescaledb psql -U kirby -d kirby_training -c "
  SELECT
    COUNT(*) as total_candles,
    COUNT(num_trades) as with_num_trades,
    MIN(num_trades) as min_trades,
    MAX(num_trades) as max_trades
  FROM candles c
  JOIN starlistings s ON c.starlisting_id = s.id
  JOIN coins co ON s.coin_id = co.id
  WHERE co.symbol = 'BTC';
"
```

## Debugging Scenarios

### Scenario 1: ">>> BINANCE BRANCH EXECUTING <<<" does NOT appear

**Problem**: Old code is running (doesn't have Binance raw API)

**Solution**:
```bash
# Verify you pulled latest code
git log --oneline -3 | grep "999794a"

# Verify you rebuilt the image
docker compose build collector

# Check when image was built
docker images | grep kirby-collector
```

### Scenario 2: Branch executes but geo-blocked

**Problem**: VPN not working

**Solution**:
```bash
# Check VPN logs
docker compose logs vpn | tail -50

# Verify VPN is connected
docker compose exec vpn curl -s https://ipinfo.io/json | grep country
# Should show: "country": "CL" (Chile) or your chosen country

# Restart VPN
docker compose restart vpn
sleep 30
```

### Scenario 3: Branch executes, API works, but num_trades still NULL

**Problem**: Normalization or database issue

**Solution**:
```bash
# Look for these lines in backfill output:
# >>> num_trades (field 8) = XXXX  ← Should be a number, not NULL
# >>> All have num_trades: True    ← Should be True, not False

# If field 8 is a number but database shows NULL, check helpers.py:
docker compose exec collector python -c "
from src.utils.helpers import normalize_candle_data
mock = [1730752800000, '68500', '68750', '68400', '68650', '1234', 1730752859999, '84567890', 5432, '617', '42345678', '0']
result = normalize_candle_data(mock, source='binance_raw')
print(f'num_trades: {result.get(\"num_trades\")}')
"
# Should output: num_trades: 5432
```

## Quick Test Script

Save this as `test_binance_digital_ocean.sh`:

```bash
#!/bin/bash
set -e

echo "=================================="
echo "Binance num_trades Debug Test"
echo "=================================="

echo "1. Checking git commit..."
git log --oneline -1 | grep "999794a" && echo "✅ Has Binance commit" || echo "❌ Missing commit - run 'git pull'"

echo ""
echo "2. Checking python-binance..."
docker compose exec collector python -c "import binance; print('✅ python-binance installed')" 2>/dev/null || echo "❌ Need to rebuild: docker compose build collector"

echo ""
echo "3. Checking VPN..."
docker compose logs vpn 2>/dev/null | grep "You are connected" | tail -1 || echo "❌ VPN not connected"

echo ""
echo "4. Running 5-minute test backfill..."
docker compose --profile vpn --profile tools run --rm collector-training \
  python -m scripts.backfill_training --coin=BTC --days=0.0035 2>&1 | \
  grep -E "(BINANCE BRANCH|num_trades|SUCCESS|FAIL)" || echo "No debug output - old code?"

echo ""
echo "5. Checking database..."
docker compose exec timescaledb psql -U kirby -d kirby_training -c \
  "SELECT COUNT(*) FILTER (WHERE num_trades IS NOT NULL) as has_trades FROM candles LIMIT 1;" 2>/dev/null

echo ""
echo "=================================="
echo "Debug test complete"
echo "=================================="
```

Run with: `chmod +x test_binance_digital_ocean.sh && ./test_binance_digital_ocean.sh`
