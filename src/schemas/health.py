"""
Pydantic schemas for health check endpoints.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollectorHealth(BaseModel):
    """Health status for a single collector."""

    exchange: str = Field(..., description="Exchange name")
    status: str = Field(..., description="Collector status")
    healthy: bool = Field(..., description="Whether collector is healthy")
    last_collection: datetime | None = Field(None, description="Last collection timestamp")
    retry_count: int = Field(..., description="Number of retries")
    last_error: str | None = Field(None, description="Last error message")
    starlistings_count: int = Field(..., description="Number of starlistings")


class HealthResponse(BaseModel):
    """Response model for overall health check."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-26T12:00:00Z",
                "database": "connected",
                "collectors": {
                    "hyperliquid": {
                        "exchange": "hyperliquid",
                        "status": "running",
                        "healthy": True,
                        "last_collection": "2025-10-26T11:59:30Z",
                        "retry_count": 0,
                        "last_error": None,
                        "starlistings_count": 8,
                    }
                },
            }
        }
    )

    status: str = Field(..., description="Overall status (healthy/degraded/unhealthy)")
    timestamp: datetime = Field(..., description="Health check timestamp")
    database: str = Field(..., description="Database connection status")
    collectors: dict[str, CollectorHealth] | None = Field(
        None, description="Collector health status"
    )


class ExchangeHealthResponse(BaseModel):
    """Response model for exchange-specific health check."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exchange": "hyperliquid",
                "collector": {
                    "exchange": "hyperliquid",
                    "status": "running",
                    "healthy": True,
                    "last_collection": "2025-10-26T11:59:30Z",
                    "retry_count": 0,
                    "last_error": None,
                    "starlistings_count": 8,
                },
                "data_freshness": {
                    "BTC/USD/perps/15m": True,
                    "SOL/USD/perps/15m": True,
                },
            }
        }
    )

    exchange: str = Field(..., description="Exchange name")
    collector: CollectorHealth = Field(..., description="Collector health")
    data_freshness: dict[str, bool] | None = Field(
        None, description="Data freshness by starlisting"
    )
