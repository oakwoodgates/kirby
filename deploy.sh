#!/bin/bash
# Kirby Quick Deployment Script
# This script automates the initial deployment of Kirby

set -e  # Exit on error

echo "========================================"
echo "  Kirby Deployment Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}[!] .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env

    # Generate random password
    RANDOM_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

    # Update password in .env
    sed -i "s/your_secure_password_here/$RANDOM_PASSWORD/g" .env

    echo -e "${GREEN}[✓] .env file created with generated password${NC}"
    echo -e "${YELLOW}[!] IMPORTANT: Your database password is: $RANDOM_PASSWORD${NC}"
    echo -e "${YELLOW}[!] Save this password securely!${NC}"
    echo ""
else
    echo -e "${GREEN}[✓] .env file already exists${NC}"
fi

# Load password from .env for training database setup
echo "Loading database password from .env..."
if [ -f .env ]; then
    # Extract POSTGRES_PASSWORD from .env file
    export $(grep "^POSTGRES_PASSWORD=" .env | xargs)
    if [ -z "$POSTGRES_PASSWORD" ]; then
        echo -e "${RED}[✗] POSTGRES_PASSWORD not found in .env file${NC}"
        exit 1
    fi
    echo -e "${GREEN}[✓] Database password loaded${NC}"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[✗] Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}[✓] Docker is installed${NC}"

# Check if Docker Compose is installed
if ! docker compose version &> /dev/null; then
    echo -e "${RED}[✗] Docker Compose is not installed${NC}"
    echo "Please install Docker Compose plugin"
    exit 1
fi
echo -e "${GREEN}[✓] Docker Compose is installed${NC}"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs backups
echo -e "${GREEN}[✓] Directories created${NC}"

# Build Docker images
echo ""
echo "Building Docker images (this may take a few minutes)..."
docker compose build

echo -e "${GREEN}[✓] Docker images built${NC}"

# Start services
echo ""
echo "Starting services..."
docker compose up -d

echo -e "${GREEN}[✓] Services started${NC}"

# Wait for database to be ready
echo ""
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if docker compose exec -T timescaledb pg_isready -U kirby &> /dev/null; then
        echo -e "${GREEN}[✓] Database is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Auto-detect and configure TimescaleDB IP for VPN
echo ""
echo "Detecting TimescaleDB IP for VPN networking..."
TIMESCALEDB_IP=$(docker inspect kirby-timescaledb -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null | head -n1)

if [ -n "$TIMESCALEDB_IP" ]; then
    echo -e "${GREEN}[✓] TimescaleDB IP detected: $TIMESCALEDB_IP${NC}"

    # Update .env file if it doesn't have TIMESCALEDB_IP set, or update it
    if grep -q "^TIMESCALEDB_IP=" .env 2>/dev/null; then
        # Update existing value
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/^TIMESCALEDB_IP=.*/TIMESCALEDB_IP=$TIMESCALEDB_IP/" .env
        else
            # Linux
            sed -i "s/^TIMESCALEDB_IP=.*/TIMESCALEDB_IP=$TIMESCALEDB_IP/" .env
        fi
        echo -e "${GREEN}[✓] Updated TIMESCALEDB_IP in .env${NC}"
    else
        # Add new line
        echo "" >> .env
        echo "# Auto-detected TimescaleDB IP (for VPN networking)" >> .env
        echo "TIMESCALEDB_IP=$TIMESCALEDB_IP" >> .env
        echo -e "${GREEN}[✓] Added TIMESCALEDB_IP to .env${NC}"
    fi
else
    echo -e "${YELLOW}[!] Could not detect TimescaleDB IP (container may not be running)${NC}"
    echo -e "${YELLOW}[!] VPN backfills may not work until IP is configured${NC}"
fi
echo ""

# Setup Production Database (kirby)
echo ""
echo "========================================"
echo "  Setting up Production Database"
echo "========================================"
echo ""

# Run migrations on production database
echo "Running production database migrations..."
docker compose exec -T collector alembic upgrade head
echo -e "${GREEN}[✓] Production migrations completed${NC}"

# Sync production configuration
echo ""
echo "Syncing production configuration..."
docker compose exec -T collector python -m scripts.sync_config
echo -e "${GREEN}[✓] Production configuration synced${NC}"

# Verify production database
echo ""
echo "Verifying production database..."
PROD_COUNT=$(docker compose exec -T timescaledb psql -U kirby -d kirby -t -c "SELECT COUNT(*) FROM starlistings;" | tr -d ' ')
echo -e "${GREEN}[✓] Production starlistings: $PROD_COUNT${NC}"

# Setup Training Database (kirby_training)
echo ""
echo "========================================"
echo "  Setting up Training Database"
echo "========================================"
echo ""

# Check if training database exists
echo "Checking if training database exists..."
DB_EXISTS=$(docker compose exec -T timescaledb psql -U kirby -t -c "SELECT 1 FROM pg_database WHERE datname='kirby_training';" | tr -d ' ')

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${GREEN}[✓] Training database already exists${NC}"
else
    echo "Creating training database..."
    docker compose exec -T timescaledb psql -U kirby -c "CREATE DATABASE kirby_training;"
    echo -e "${GREEN}[✓] Training database created${NC}"
fi

# Enable TimescaleDB extension on training database
echo ""
echo "Enabling TimescaleDB extension..."
docker compose exec -T timescaledb psql -U kirby -d kirby_training -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
echo -e "${GREEN}[✓] TimescaleDB extension enabled${NC}"

# Run migrations on training database
echo ""
echo "Running training database migrations..."
docker compose exec -T collector python -m scripts.migrate_training_db
echo -e "${GREEN}[✓] Training migrations completed${NC}"

# Sync training configuration
echo ""
echo "Syncing training configuration..."
# Container already has correct TRAINING_DATABASE_URL from docker-compose.yml
docker compose exec -T collector python -m scripts.sync_training_config
echo -e "${GREEN}[✓] Training configuration synced${NC}"

# Verify training database
echo ""
echo "Verifying training database..."
TRAINING_COUNT=$(docker compose exec -T timescaledb psql -U kirby -d kirby_training -t -c "SELECT COUNT(*) FROM starlistings;" | tr -d ' ')
echo -e "${GREEN}[✓] Training starlistings: $TRAINING_COUNT${NC}"

# Check health
echo ""
echo "Checking API health..."
sleep 5
HEALTH_CHECK=$(curl -s http://localhost:8000/health || echo "failed")

if [[ $HEALTH_CHECK == *"healthy"* ]]; then
    echo -e "${GREEN}[✓] API is healthy${NC}"
else
    echo -e "${YELLOW}[!] API health check inconclusive${NC}"
    echo "Response: $HEALTH_CHECK"
fi

# Final verification
echo ""
echo "========================================"
echo "  Final Verification"
echo "========================================"
echo ""
echo "Running comprehensive verification..."
docker compose exec -T collector python -m scripts.verify_deployment

# Display status
echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "Services Status:"
docker compose ps
echo ""
echo -e "${GREEN}Database Summary:${NC}"
echo "  Production DB (kirby):  $PROD_COUNT starlistings"
echo "  Training DB (kirby_training): $TRAINING_COUNT starlistings"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Check collector logs: docker compose logs -f collector"
echo "2. Check API: curl http://localhost:8000/health"
echo "3. View production starlistings: curl http://localhost:8000/starlistings"
echo "4. Wait 1-2 minutes for data collection to start"
echo "5. Check production candles: curl http://localhost:8000/candles/hyperliquid/BTC/USD/perps/1m?limit=5"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- API is running on: http://localhost:8000"
echo "- Production collector is running in the background"
echo "- Both databases are set up and ready"
echo "- Database data is persisted in Docker volumes"
echo ""
echo -e "${GREEN}Training Database:${NC}"
echo "- To backfill training data from Binance:"
echo "  docker compose exec collector python -m scripts.backfill_training --coin=BTC --days=7"
echo "- Requires VPN if Binance geo-restricts your region"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose stop"
echo "To restart: docker compose start"
echo ""
