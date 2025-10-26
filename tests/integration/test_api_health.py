"""
Integration tests for health check endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.main import app


@pytest.mark.integration
class TestHealthEndpoints:
    """Test health check API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, db_session: AsyncSession):
        """Test that health check returns success with database connection."""

        # Override dependency to use test database
        async def override_get_db_session():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db_session

        try:
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "timestamp" in data
            assert "database" in data
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_exchange_health_check_not_implemented(self, db_session: AsyncSession):
        """Test that exchange-specific health check returns 501."""

        # Override dependency to use test database
        async def override_get_db_session():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db_session

        try:
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/hyperliquid")

            assert response.status_code == 501
            data = response.json()
            assert "detail" in data
            assert "not yet implemented" in data["detail"].lower()
        finally:
            app.dependency_overrides.clear()
