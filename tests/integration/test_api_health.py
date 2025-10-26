"""
Integration tests for health check endpoints.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestHealthEndpoints:
    """Test health check API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, async_client: AsyncClient):
        """Test that health check returns success with database connection."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "database" in data
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_exchange_health_check_not_implemented(self, async_client: AsyncClient):
        """Test that exchange-specific health check returns 501."""
        response = await async_client.get("/health/hyperliquid")

        assert response.status_code == 501
        data = response.json()
        assert "detail" in data
        assert "not yet implemented" in data["detail"].lower()
