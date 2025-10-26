"""
API router for health check endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.schemas.health import HealthResponse
from src.utils.helpers import utc_now

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Overall health check",
    description="Check the overall health of the Kirby system",
)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    """
    Perform overall system health check.

    Checks:
    - Database connectivity
    - Collector status (if available)

    Returns:
    - Health status with details
    """
    # Check database connection
    try:
        await session.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"

    # Determine overall status
    overall_status = "healthy" if database_status == "connected" else "unhealthy"

    # Note: Collector health would require shared state/cache
    # For MVP, we'll just return database health
    # In production, this could check a Redis cache or collector status endpoint

    return HealthResponse(
        status=overall_status,
        timestamp=utc_now(),
        database=database_status,
        collectors=None,  # Would populate this if we had collector status available
    )


@router.get(
    "/{exchange}",
    summary="Exchange health check",
    description="Check health for a specific exchange collector",
)
async def exchange_health_check(
    exchange: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Check health for a specific exchange.

    Note: This endpoint is a placeholder for future implementation.
    Requires shared state between API and collectors (e.g., Redis).

    Parameters:
    - **exchange**: Exchange name (e.g., 'hyperliquid')

    Returns:
    - Exchange-specific health status
    """
    # This would require access to collector state
    # For MVP, we'll return a not implemented response
    raise HTTPException(
        status_code=501,
        detail="Exchange-specific health checks not yet implemented. Use /health for overall status.",
    )
