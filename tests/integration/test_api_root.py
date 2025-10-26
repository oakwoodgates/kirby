"""
Integration tests for root API endpoint.
"""
import pytest
from httpx import AsyncClient

from src.api.main import app


@pytest.mark.integration
class TestRootEndpoint:
    """Test root API endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test that root endpoint returns API information."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "environment" in data

        assert data["name"] == "Kirby API"
        assert data["version"] == "0.1.0"
        assert "market data" in data["description"].lower()
