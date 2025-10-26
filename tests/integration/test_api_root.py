"""
Integration tests for root API endpoint.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestRootEndpoint:
    """Test root API endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, async_client: AsyncClient):
        """Test that root endpoint returns API information."""
        response = await async_client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "environment" in data

        assert data["name"] == "Kirby API"
        assert data["version"] == "0.1.0"
        assert "market data" in data["description"].lower()
