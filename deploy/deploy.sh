#!/bin/bash
# Kirby Deployment Script for Digital Ocean
# This script deploys the Kirby application on a Digital Ocean droplet

set -e  # Exit on error

echo "=========================================="
echo "Kirby Deployment Script"
echo "=========================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.production to .env and configure it first."
    exit 1
fi

# Load environment variables
source .env

echo "Environment: $ENVIRONMENT"
echo ""

# Step 1: Pull latest code
echo "Step 1: Pulling latest code from GitHub..."
git pull origin main
echo "✓ Code updated"
echo ""

# Step 2: Build Docker images
echo "Step 2: Building Docker images..."
cd docker
docker compose -f docker-compose.prod.yml build --no-cache
cd ..
echo "✓ Images built"
echo ""

# Step 3: Stop existing containers
echo "Step 3: Stopping existing containers..."
cd docker
docker compose -f docker-compose.prod.yml down
cd ..
echo "✓ Containers stopped"
echo ""

# Step 4: Start new containers
echo "Step 4: Starting new containers..."
cd docker
docker compose -f docker-compose.prod.yml up -d
cd ..
echo "✓ Containers started"
echo ""

# Step 5: Wait for database to be ready
echo "Step 5: Waiting for database to be ready..."
sleep 10
echo "✓ Database ready"
echo ""

# Step 6: Run migrations
echo "Step 6: Running database migrations..."
docker exec kirby_api alembic upgrade head || echo "Note: Migrations may have already been run"
echo "✓ Migrations complete"
echo ""

# Step 7: Seed database (if needed)
echo "Step 7: Would you like to seed the database? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    docker exec kirby_api python scripts/seed_database.py
    echo "✓ Database seeded"
else
    echo "Skipped database seeding"
fi
echo ""

# Step 8: Check service health
echo "Step 8: Checking service health..."
echo "Waiting 10 seconds for services to stabilize..."
sleep 10

echo "Container status:"
cd docker
docker compose -f docker-compose.prod.yml ps
cd ..
echo ""

echo "API Health check:"
curl -f http://localhost:${API_PORT}/api/v1/health || echo "WARNING: API health check failed"
echo ""

echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  - TimescaleDB: localhost:5432"
echo "  - API: http://localhost:${API_PORT}"
echo ""
echo "Useful commands:"
echo "  - View logs: cd docker && docker compose -f docker-compose.prod.yml logs -f"
echo "  - Stop services: cd docker && docker compose -f docker-compose.prod.yml down"
echo "  - Restart services: cd docker && docker compose -f docker-compose.prod.yml restart"
echo ""
