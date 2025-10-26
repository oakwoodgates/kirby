# Testing Guide

## Overview

Kirby includes a comprehensive test suite covering:
- **Unit tests**: Testing individual functions and utilities
- **Integration tests**: Testing API endpoints, database operations, and repositories
- **Coverage reporting**: Tracking test coverage metrics

## Quick Start

### Prerequisites

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. Ensure PostgreSQL is running (via Docker Compose):
```bash
docker compose up -d timescaledb
```

### Running Tests

#### Run all tests with coverage:
```bash
python scripts/run_tests.py
```

This will:
- Create/reset the test database (`kirby_test`)
- Run all unit and integration tests
- Generate coverage reports (terminal + HTML)

#### Run tests directly with pytest:
```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_helpers.py

# Specific test
pytest tests/unit/test_helpers.py::TestValidateCandle::test_validate_valid_candle

# With verbose output
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

#### Run tests by marker:
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── __init__.py
│   └── test_helpers.py     # Tests for utility functions
└── integration/             # Integration tests
    ├── __init__.py
    ├── test_api_root.py     # Root endpoint tests
    ├── test_api_health.py   # Health check tests
    ├── test_api_starlistings.py  # Starlisting endpoint tests
    ├── test_api_candles.py  # Candle data endpoint tests
    └── test_repositories.py # Database repository tests
```

## Key Fixtures

### Database Fixtures
- `test_db_engine`: Creates a fresh test database for each test function
- `db_session`: Provides a database session with automatic rollback
- `seed_base_data`: Seeds reference data (exchanges, coins, intervals, etc.)
- `seed_starlistings`: Creates test starlistings

### API Fixtures
- `test_client`: Synchronous FastAPI test client
- `async_client`: Asynchronous FastAPI test client

## Writing Tests

### Unit Test Example
```python
import pytest
from src.utils.helpers import validate_candle

@pytest.mark.unit
def test_validate_valid_candle():
    """Test that valid candle passes validation."""
    candle = {
        "time": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "open": 40000.0,
        "high": 40500.0,
        "low": 39800.0,
        "close": 40200.0,
        "volume": 1234.56,
    }
    assert validate_candle(candle) is True
```

### Integration Test Example
```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_candles(db_session, seed_base_data, seed_starlistings):
    """Test getting candle data."""
    # Override dependency to use test database
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/candles/hyperliquid/BTC/USD/perps/1m")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
    finally:
        app.dependency_overrides.clear()
```

## Coverage Reports

After running tests with coverage, you can view:

- **Terminal report**: Shows coverage summary in the console
- **HTML report**: Open `htmlcov/index.html` in your browser for detailed coverage

## Continuous Integration

Tests are designed to run in CI environments. The test database is automatically created and cleaned up.

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running: `docker compose up -d timescaledb`
- Check database credentials in `.env`
- Test database uses `kirby_test` instead of `kirby`

### Import Errors
- Install dev dependencies: `pip install -e ".[dev]"`
- Ensure you're in the project root directory

### Async Test Issues
- pytest-asyncio should be installed
- Use `@pytest.mark.asyncio` decorator for async tests
- Use `async def test_...` for async test functions

## Test Coverage Goals

- **Unit tests**: >90% coverage of utility functions
- **Integration tests**: All API endpoints covered
- **Repository tests**: All CRUD operations tested
- **Overall**: >80% code coverage
