#!/bin/bash
# Setup script for Kirby development environment

set -e

echo "🚀 Setting up Kirby development environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and update the database password!"
else
    echo "✅ .env file already exists"
fi

# Check if alembic.ini exists
if [ ! -f alembic.ini ]; then
    echo "📝 Creating alembic.ini from template..."
    cp alembic.ini.template alembic.ini
else
    echo "✅ alembic.ini already exists"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🐳 Starting TimescaleDB with Docker Compose..."
cd docker
docker-compose up -d timescaledb
cd ..

echo "⏳ Waiting for TimescaleDB to be ready..."
sleep 5

# Wait for database to be healthy
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker-compose -f docker/docker-compose.yml exec -T timescaledb pg_isready -U kirby_user > /dev/null 2>&1; then
        echo "✅ TimescaleDB is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ TimescaleDB failed to start in time"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and update POSTGRES_PASSWORD"
echo "2. Install dependencies: poetry install"
echo "3. Run migrations: alembic upgrade head"
echo "4. Start development server: uvicorn src.api.main:app --reload"
echo ""
echo "Or use Docker Compose:"
echo "  cd docker && docker-compose up"
