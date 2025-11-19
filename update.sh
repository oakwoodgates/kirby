#!/bin/bash

#################################################################################
# Kirby Fast Update Script
#################################################################################
#
# Purpose: Quick updates for code changes, config updates, or migrations
#          without the overhead of full deployment
#
# Usage:
#   ./update.sh                  # Auto-detect what changed and update
#   ./update.sh --force-build    # Force rebuild even if no code changes
#   ./update.sh --force-migrate  # Force migration check even if up to date
#   ./update.sh --skip-build     # Skip build (config/docs changes only)
#
# Speed Comparison:
#   Full deploy.sh:  5-10 minutes
#   update.sh:       30-60 seconds (typical)
#                    10-20 seconds (restart only)
#
#################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FORCE_BUILD=false
FORCE_MIGRATE=false
SKIP_BUILD=false
AUTO_BACKFILL=false
SKIP_BACKFILL=false

for arg in "$@"; do
    case $arg in
        --force-build)
            FORCE_BUILD=true
            shift
            ;;
        --force-migrate)
            FORCE_MIGRATE=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --auto-backfill)
            AUTO_BACKFILL=true
            shift
            ;;
        --skip-backfill)
            SKIP_BACKFILL=true
            shift
            ;;
        --help)
            echo "Usage: ./update.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --force-build      Force rebuild even if no code changes"
            echo "  --force-migrate    Force migration check"
            echo "  --skip-build       Skip build (config/docs changes only)"
            echo "  --auto-backfill    Automatically backfill detected gaps"
            echo "  --skip-backfill    Skip downtime detection and backfill"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Kirby Fast Update Script                          ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo ""

START_TIME=$(date +%s)

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if services are running
if ! docker compose ps | grep -q "timescaledb"; then
    echo -e "${RED}Error: Services are not running. Use deploy.sh for initial deployment${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is running"
echo -e "${GREEN}✓${NC} Services are running"
echo ""

#################################################################################
# Step 1: Check for code changes
#################################################################################

echo -e "${BLUE}[1/6]${NC} Checking for changes..."

# Store current git commit before pull
BEFORE_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Pull latest changes
if git pull origin $(git branch --show-current) 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Git pull successful"
else
    echo -e "${YELLOW}⚠${NC}  Not a git repository or pull failed, continuing anyway..."
fi

AFTER_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Check if code changed
CODE_CHANGED=false
if [ "$BEFORE_COMMIT" != "$AFTER_COMMIT" ]; then
    # Check what changed
    if git diff --name-only "$BEFORE_COMMIT" "$AFTER_COMMIT" | grep -qE '\.(py|txt|toml|Dockerfile|dockerignore)$'; then
        CODE_CHANGED=true
        echo -e "${YELLOW}⚠${NC}  Code changes detected"
    else
        echo -e "${GREEN}✓${NC} No code changes (only docs/config)"
    fi
else
    echo -e "${GREEN}✓${NC} No new commits"
fi

echo ""

#################################################################################
# Step 2: Build Docker images (conditional)
#################################################################################

NEED_BUILD=false

if [ "$FORCE_BUILD" = true ]; then
    NEED_BUILD=true
    echo -e "${BLUE}[2/6]${NC} Building Docker images (forced)..."
elif [ "$SKIP_BUILD" = true ]; then
    NEED_BUILD=false
    echo -e "${BLUE}[2/6]${NC} Skipping Docker build (--skip-build flag)"
elif [ "$CODE_CHANGED" = true ]; then
    NEED_BUILD=true
    echo -e "${BLUE}[2/6]${NC} Building Docker images (code changed)..."
else
    echo -e "${BLUE}[2/6]${NC} Skipping Docker build (no code changes)"
fi

if [ "$NEED_BUILD" = true ]; then
    BUILD_START=$(date +%s)

    if docker compose build --quiet 2>&1 | grep -q "Error"; then
        echo -e "${RED}✗${NC} Docker build failed"
        exit 1
    fi

    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))

    echo -e "${GREEN}✓${NC} Docker images built (${BUILD_TIME}s)"
fi

echo ""

#################################################################################
# Step 3: Check for new migrations
#################################################################################

echo -e "${BLUE}[3/6]${NC} Checking for database migrations..."

NEED_MIGRATE=false

if [ "$FORCE_MIGRATE" = true ]; then
    NEED_MIGRATE=true
    echo -e "${YELLOW}⚠${NC}  Forced migration check"
else
    # Check if migrations are up to date
    CURRENT_REV=$(docker compose exec -T collector alembic current 2>/dev/null | grep -oP '(?<=\(head\)|^)[a-f0-9]+' | head -1 || echo "none")
    HEAD_REV=$(docker compose exec -T collector alembic heads 2>/dev/null | grep -oP '^[a-f0-9]+' | head -1 || echo "none")

    if [ "$CURRENT_REV" != "$HEAD_REV" ]; then
        NEED_MIGRATE=true
        echo -e "${YELLOW}⚠${NC}  New migrations detected ($CURRENT_REV -> $HEAD_REV)"
    else
        echo -e "${GREEN}✓${NC} Database is up to date (revision: $CURRENT_REV)"
    fi
fi

if [ "$NEED_MIGRATE" = true ]; then
    echo "  Running migrations on production database..."

    if docker compose exec -T collector alembic upgrade head; then
        echo -e "${GREEN}✓${NC} Production database migrated"
    else
        echo -e "${RED}✗${NC} Production migration failed"
        exit 1
    fi

    # Check if training database exists
    if docker compose exec -T timescaledb psql -U kirby -lqt | cut -d \| -f 1 | grep -qw kirby_training; then
        echo "  Running migrations on training database..."

        if docker compose exec -T collector python -m scripts.migrate_training_db; then
            echo -e "${GREEN}✓${NC} Training database migrated"
        else
            echo -e "${YELLOW}⚠${NC}  Training migration failed (non-critical)"
        fi
    fi
fi

echo ""

#################################################################################
# Step 4: Restart services
#################################################################################

echo -e "${BLUE}[4/6]${NC} Restarting services..."

RESTART_START=$(date +%s)

# Use restart (fast) instead of down/up (slow)
if docker compose restart collector api 2>&1; then
    RESTART_END=$(date +%s)
    RESTART_TIME=$((RESTART_END - RESTART_START))

    echo -e "${GREEN}✓${NC} Services restarted (${RESTART_TIME}s)"
else
    echo -e "${RED}✗${NC} Service restart failed"
    exit 1
fi

# Give services a moment to initialize
sleep 3

echo ""

#################################################################################
# Step 5: Health check
#################################################################################

echo -e "${BLUE}[5/6]${NC} Verifying services..."

# Check database
if docker compose exec -T timescaledb pg_isready -U kirby > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Database is healthy"
else
    echo -e "${RED}✗${NC} Database health check failed"
    exit 1
fi

# Check API
sleep 2  # Give API a moment to start
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} API is healthy"
else
    echo -e "${YELLOW}⚠${NC}  API health check failed (may still be starting)"
fi

# Check collector (look for recent logs)
COLLECTOR_RUNNING=$(docker compose ps collector | grep -c "running" 2>/dev/null || echo "0")
COLLECTOR_RUNNING=$(echo "$COLLECTOR_RUNNING" | tr -d '\n\r' | head -c 1)
if [ "$COLLECTOR_RUNNING" -gt 0 2>/dev/null ]; then
    echo -e "${GREEN}✓${NC} Collector is running"
else
    echo -e "${RED}✗${NC} Collector is not running"
fi

echo ""

#################################################################################
# Step 6: Display status
#################################################################################

echo -e "${BLUE}[6/7]${NC} Update summary..."

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║             Update Completed Successfully                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total time: ${GREEN}${TOTAL_TIME}s${NC}"
echo ""
echo -e "  Changes applied:"
if [ "$NEED_BUILD" = true ]; then
    echo -e "    ${GREEN}✓${NC} Docker images rebuilt"
else
    echo -e "    ${BLUE}○${NC} Docker images unchanged"
fi

if [ "$NEED_MIGRATE" = true ]; then
    echo -e "    ${GREEN}✓${NC} Database migrations applied"
else
    echo -e "    ${BLUE}○${NC} No new migrations"
fi

echo -e "    ${GREEN}✓${NC} Services restarted"
echo ""

echo -e "  Service Status:"
docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo -e "${YELLOW}Recent collector logs:${NC}"
docker compose logs --tail=10 collector
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo -e "  • Check logs: ${YELLOW}docker compose logs -f collector api${NC}"
echo -e "  • Check health: ${YELLOW}curl http://localhost:8000/health${NC}"
echo ""

#################################################################################
# Step 7: Detect and backfill downtime (optional)
#################################################################################

if [ "$SKIP_BACKFILL" = false ]; then
    echo -e "${BLUE}[7/7]${NC} Checking for data gaps..."
    echo ""

    # Run downtime detection
    DOWNTIME_JSON=$(docker compose exec -T collector python -m scripts.detect_downtime 2>/dev/null || echo "{}")

    if [ "$DOWNTIME_JSON" = "{}" ]; then
        echo -e "${YELLOW}⚠${NC}  Could not detect downtime (collector may still be starting)"
        echo -e "  Run manually later: ${YELLOW}./backfill_downtime.sh${NC}"
        echo ""
    else
        # Parse gap information
        MAX_GAP_MINUTES=$(echo "$DOWNTIME_JSON" | grep -oP '"max_gap_minutes":\s*\K\d+' | head -1)
        MAX_GAP_HOURS=$(echo "$DOWNTIME_JSON" | grep -oP '"max_gap_hours":\s*\K[0-9.]+' | head -1)

        if [ -z "$MAX_GAP_MINUTES" ]; then
            MAX_GAP_MINUTES=0
        fi

        if [ "$MAX_GAP_MINUTES" -gt 5 ]; then
            echo -e "${YELLOW}⚠${NC}  Data gap detected: ${YELLOW}${MAX_GAP_HOURS} hours${NC} (${MAX_GAP_MINUTES} minutes)"
            echo ""
            echo "  Data recovery available:"
            echo -e "    ${GREEN}✓${NC} Candles (OHLCV) - 100% recoverable"
            echo -e "    ${YELLOW}⚠${NC}  Funding rates - 40% recoverable (rate + premium only)"
            echo -e "    ${RED}✗${NC} Open interest - NOT recoverable (permanently lost)"
            echo ""

            if [ "$AUTO_BACKFILL" = true ]; then
                echo -e "${GREEN}Auto-backfill enabled${NC} - Running backfill now..."
                echo ""

                if ./backfill_downtime.sh; then
                    echo ""
                    echo -e "${GREEN}✓${NC} Data backfill completed"
                else
                    echo ""
                    echo -e "${RED}✗${NC} Backfill failed - run manually: ${YELLOW}./backfill_downtime.sh${NC}"
                fi
            else
                # Prompt user
                echo -ne "${BLUE}Run backfill now? [y/N]:${NC} "
                read -r response

                if [[ "$response" =~ ^[Yy]$ ]]; then
                    echo ""
                    if ./backfill_downtime.sh; then
                        echo ""
                        echo -e "${GREEN}✓${NC} Data backfill completed"
                    else
                        echo ""
                        echo -e "${RED}✗${NC} Backfill failed"
                    fi
                else
                    echo ""
                    echo -e "  Skipped - run manually later: ${YELLOW}./backfill_downtime.sh${NC}"
                fi
            fi
        else
            echo -e "${GREEN}✓${NC} No significant data gaps detected (< 5 minutes)"
            echo -e "  Last data: ${MAX_GAP_MINUTES} minutes ago"
        fi
        echo ""
    fi
else
    echo ""
    echo -e "${BLUE}Downtime detection skipped${NC} (--skip-backfill flag)"
    echo -e "  Run manually if needed: ${YELLOW}./backfill_downtime.sh${NC}"
    echo ""
fi
