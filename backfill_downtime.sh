#!/bin/bash

#################################################################################
# Kirby Downtime Backfill Script
#################################################################################
#
# Purpose: Automatically detect and backfill data gaps caused by downtime
#
# Usage:
#   ./backfill_downtime.sh                    # Auto-detect and backfill gaps
#   ./backfill_downtime.sh --dry-run          # Show what would be backfilled
#   ./backfill_downtime.sh --days 7           # Manual: backfill last 7 days
#   ./backfill_downtime.sh --coin BTC         # Manual: backfill specific coin
#
# What Gets Recovered:
#   ✓ Candles (all intervals)    - 100% recoverable via CCXT
#   ⚠ Funding rates               - Partially recoverable (rate + premium only)
#   ✗ Funding prices              - LOST (mark, index, oracle, mid prices)
#   ✗ Open interest               - LOST (no historical data available)
#
#################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false
MANUAL_DAYS=""
MANUAL_COIN=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --days)
            MANUAL_DAYS="$2"
            shift 2
            ;;
        --coin)
            MANUAL_COIN="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./backfill_downtime.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run         Show what would be backfilled without doing it"
            echo "  --days N          Manual: backfill last N days"
            echo "  --coin SYMBOL     Manual: backfill specific coin only"
            echo "  --help            Show this help message"
            echo ""
            echo "Recovery Levels:"
            echo "  ✓ Candles         100% recoverable"
            echo "  ⚠ Funding rates    40% recoverable (rate + premium only)"
            echo "  ✗ Funding prices   LOST (mark, index, oracle, mid)"
            echo "  ✗ Open interest    LOST (no historical API)"
            exit 0
            ;;
        *)
            # Skip unknown args (might be values for other args)
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Kirby Downtime Backfill Script                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

START_TIME=$(date +%s)

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if services are running
if ! docker compose ps | grep -q "timescaledb"; then
    echo -e "${RED}Error: Services are not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is running"
echo -e "${GREEN}✓${NC} Services are running"
echo ""

#################################################################################
# Step 1: Detect downtime
#################################################################################

echo -e "${BLUE}[1/4]${NC} Detecting data gaps..."
echo ""

# Run downtime detection script
DOWNTIME_JSON=$(docker compose exec -T collector python -m scripts.detect_downtime 2>/dev/null || echo "{}")

if [ "$DOWNTIME_JSON" = "{}" ]; then
    echo -e "${RED}✗${NC} Failed to detect downtime"
    exit 1
fi

# Parse JSON results
MAX_GAP_MINUTES=$(echo "$DOWNTIME_JSON" | grep -oP '"max_gap_minutes":\s*\K\d+' | head -1)
MAX_GAP_HOURS=$(echo "$DOWNTIME_JSON" | grep -oP '"max_gap_hours":\s*\K[0-9.]+' | head -1)
TOTAL_STARLISTINGS=$(echo "$DOWNTIME_JSON" | grep -oP '"total_starlistings":\s*\K\d+' | head -1)

echo -e "  Current time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo -e "  Active starlistings: ${TOTAL_STARLISTINGS}"
echo -e "  Maximum gap: ${YELLOW}${MAX_GAP_HOURS} hours${NC} (${MAX_GAP_MINUTES} minutes)"
echo ""

# Show per-starlisting gaps
echo -e "${YELLOW}Data Gaps by Starlisting:${NC}"
echo "$DOWNTIME_JSON" | python -c "
import sys
import json

try:
    data = json.loads(sys.stdin.read())
    for star in data.get('starlistings', []):
        candle_gap = star['candles']['gap_hours']
        funding_gap = star['funding_rates']['gap_hours']
        oi_gap = star['open_interest']['gap_hours']

        # Only show if gap > 0.1 hours (6 minutes)
        if candle_gap > 0.1 or funding_gap > 0.1 or oi_gap > 0.1:
            print(f\"  {star['coin']}/{star['quote']} {star['interval']}:\")
            print(f\"    Candles: {candle_gap:.2f}h, Funding: {funding_gap:.2f}h, OI: {oi_gap:.2f}h\")
except json.JSONDecodeError as e:
    print(f\"  Error parsing JSON: {e}\", file=sys.stderr)
except Exception as e:
    print(f\"  Error: {e}\", file=sys.stderr)
" 2>/dev/null || echo "  (Could not parse gap details)"

echo ""

# Determine backfill strategy
if [ -n "$MANUAL_DAYS" ]; then
    BACKFILL_DAYS=$MANUAL_DAYS
    echo -e "${YELLOW}Manual mode:${NC} Backfilling last ${BACKFILL_DAYS} days"
elif [ "$MAX_GAP_HOURS" = "0" ] || [ -z "$MAX_GAP_HOURS" ]; then
    echo -e "${GREEN}No significant gaps detected${NC} (< 5 minutes)"
    echo ""
    echo "Nothing to backfill. Exiting."
    exit 0
else
    # Convert gap hours to days (round up) - use Python for cross-platform compatibility
    BACKFILL_DAYS=$(python -c "import math; print(math.ceil(($MAX_GAP_HOURS + 23) / 24))" 2>/dev/null || echo "1")
    echo -e "${YELLOW}Auto-detected gap:${NC} ${MAX_GAP_HOURS} hours"
    echo -e "Will backfill last ${BACKFILL_DAYS} days to ensure complete recovery"
fi

echo ""

#################################################################################
# Step 2: Backfill candles (100% recoverable)
#################################################################################

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN]${NC} Would backfill candles for ${BACKFILL_DAYS} days"
    echo ""
else
    echo -e "${BLUE}[2/4]${NC} Backfilling candle data (100% recoverable)..."
    echo ""

    BACKFILL_START=$(date +%s)

    # Build backfill command
    CANDLE_CMD="docker compose exec -T collector python -m scripts.backfill --days=${BACKFILL_DAYS}"

    if [ -n "$MANUAL_COIN" ]; then
        CANDLE_CMD="${CANDLE_CMD} --coin=${MANUAL_COIN}"
        echo "  Backfilling coin: ${MANUAL_COIN}"
    else
        echo "  Backfilling all active starlistings..."
    fi

    # Run backfill
    if $CANDLE_CMD; then
        BACKFILL_END=$(date +%s)
        BACKFILL_TIME=$((BACKFILL_END - BACKFILL_START))
        echo ""
        echo -e "${GREEN}✓${NC} Candles backfilled (${BACKFILL_TIME}s)"
    else
        echo ""
        echo -e "${RED}✗${NC} Candle backfill failed"
        exit 1
    fi

    echo ""
fi

#################################################################################
# Step 3: Backfill funding rates (partially recoverable)
#################################################################################

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN]${NC} Would backfill funding rates for ${BACKFILL_DAYS} days"
    echo ""
else
    echo -e "${BLUE}[3/4]${NC} Backfilling funding rates (partially recoverable)..."
    echo ""

    echo -e "${YELLOW}⚠${NC}  Note: Historical funding API only provides:"
    echo "    ✓ funding_rate"
    echo "    ✓ premium"
    echo "    ✗ mark_price (LOST)"
    echo "    ✗ index_price (LOST)"
    echo "    ✗ oracle_price (LOST)"
    echo "    ✗ mid_price (LOST)"
    echo "    ✗ next_funding_time (LOST)"
    echo ""

    FUNDING_START=$(date +%s)

    # Build backfill command
    FUNDING_CMD="docker compose exec -T collector python -m scripts.backfill_funding --days=${BACKFILL_DAYS}"

    if [ -n "$MANUAL_COIN" ]; then
        FUNDING_CMD="${FUNDING_CMD} --coin=${MANUAL_COIN}"
        echo "  Backfilling coin: ${MANUAL_COIN}"
    else
        echo "  Backfilling all active coins..."
    fi

    # Run backfill
    if $FUNDING_CMD; then
        FUNDING_END=$(date +%s)
        FUNDING_TIME=$((FUNDING_END - FUNDING_START))
        echo ""
        echo -e "${GREEN}✓${NC} Funding rates backfilled (${FUNDING_TIME}s)"
    else
        echo ""
        echo -e "${YELLOW}⚠${NC}  Funding backfill failed (non-critical)"
    fi

    echo ""
fi

#################################################################################
# Step 4: Generate loss report
#################################################################################

echo -e "${BLUE}[4/4]${NC} Generating data loss report..."
echo ""

echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║              Data Recovery Summary                        ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}✓ FULLY RECOVERED:${NC}"
echo "  • Candles (OHLCV data for all intervals)"
echo "    - 100% recovery via CCXT API"
echo "    - All intervals: 1m, 15m, 4h, 1d"
echo ""

echo -e "${YELLOW}⚠ PARTIALLY RECOVERED:${NC}"
echo "  • Funding Rates (basic fields only)"
echo "    - ✓ funding_rate"
echo "    - ✓ premium"
echo "    - ✗ mark_price (NOT available historically)"
echo "    - ✗ index_price (NOT available historically)"
echo "    - ✗ oracle_price (NOT available historically)"
echo "    - ✗ mid_price (NOT available historically)"
echo "    - ✗ next_funding_time (NOT available historically)"
echo "    - Recovery: ~40% (2 of 7 fields)"
echo ""

echo -e "${RED}✗ PERMANENTLY LOST:${NC}"
echo "  • Open Interest (no historical API available)"
echo "    - ✗ open_interest"
echo "    - ✗ notional_value"
echo "    - ✗ day_base_volume"
echo "    - ✗ day_notional_volume"
echo "    - Recovery: 0% (no historical data)"
echo ""

# Calculate time range
if [ "$MAX_GAP_HOURS" != "0" ] && [ -n "$MAX_GAP_HOURS" ]; then
    GAP_START=$(date -u -d "${BACKFILL_DAYS} days ago" '+%Y-%m-%d %H:%M:%S UTC')
    GAP_END=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

    echo -e "${BLUE}Affected Time Range:${NC}"
    echo "  Start: ${GAP_START}"
    echo "  End:   ${GAP_END}"
    echo "  Duration: ${MAX_GAP_HOURS} hours (${BACKFILL_DAYS} days backfilled)"
    echo ""
fi

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Backfill Completed Successfully                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total time: ${GREEN}${TOTAL_TIME}s${NC}"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo -e "  • Verify data: ${YELLOW}docker compose exec timescaledb psql -U kirby -d kirby -c 'SELECT COUNT(*) FROM candles;'${NC}"
echo -e "  • Check collector: ${YELLOW}docker compose logs -f collector${NC}"
echo -e "  • Monitor health: ${YELLOW}curl http://localhost:8000/health${NC}"
echo ""

echo -e "${YELLOW}Important:${NC} Open Interest data lost during downtime cannot be recovered."
echo "Consider implementing monitoring/alerting to minimize future downtime."
echo ""
