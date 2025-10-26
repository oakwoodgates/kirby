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

# Run migrations
echo ""
echo "Running database migrations..."
docker compose exec -T collector alembic upgrade head
echo -e "${GREEN}[✓] Migrations completed${NC}"

# Sync configuration
echo ""
echo "Syncing configuration..."
docker compose exec -T collector python -m scripts.sync_config
echo -e "${GREEN}[✓] Configuration synced${NC}"

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

# Display status
echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "Services Status:"
docker compose ps
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Check collector logs: docker compose logs -f collector"
echo "2. Check API: curl http://localhost:8000/health"
echo "3. View starlistings: curl http://localhost:8000/starlistings"
echo "4. Wait 1-2 minutes for data collection to start"
echo "5. Check candles: curl http://localhost:8000/candles/hyperliquid/BTC/USD/perps/1m?limit=5"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- API is running on: http://localhost:8000"
echo "- Collector is running in the background"
echo "- Database data is persisted in Docker volume"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose stop"
echo "To restart: docker compose start"
echo ""
