#!/bin/bash
# Development environment setup script

set -e

echo "===== Kirby Development Setup ====="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.11+"
    exit 1
fi

echo "Step 1: Creating virtual environment..."
python3 -m venv venv

echo "Step 2: Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

echo "Step 3: Upgrading pip..."
pip install --upgrade pip

echo "Step 4: Installing Kirby with dev dependencies..."
pip install -e ".[dev]"

echo ""
echo "===== Setup Complete! ====="
echo ""
echo "To activate the virtual environment:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "  source venv/Scripts/activate"
else
    echo "  source venv/bin/activate"
fi
echo ""
echo "To run tests:"
echo "  python scripts/run_tests.py"
echo ""
echo "To start the database:"
echo "  docker compose up -d timescaledb"
echo ""
