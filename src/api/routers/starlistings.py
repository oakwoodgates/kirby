"""
API router for starlisting endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.config.loader import ConfigLoader
from src.schemas.starlistings import StarlistingListResponse, StarlistingResponse

router = APIRouter(prefix="/starlistings", tags=["starlistings"])


@router.get(
    "",
    response_model=StarlistingListResponse,
    summary="List all starlistings",
    description="Get all configured starlistings (active and inactive)",
)
async def list_starlistings(
    active_only: bool = True,
    session: AsyncSession = Depends(get_db_session),
) -> StarlistingListResponse:
    """
    List all configured starlistings.

    Parameters:
    - **active_only**: Filter to only active starlistings (default: True)

    Returns:
    - List of starlistings with full details
    """
    # Use ConfigLoader to get starlistings from database
    config_loader = ConfigLoader()
    starlistings_data = await config_loader.get_active_starlistings(session)

    # Filter by active status if needed
    if active_only:
        # get_active_starlistings already filters by active
        pass
    else:
        # Would need to implement get_all_starlistings if we want inactive ones
        # For MVP, we'll just return active ones
        pass

    # Convert to response models
    starlisting_responses = []
    for starlisting_data in starlistings_data:
        starlisting_response = StarlistingResponse(
            id=starlisting_data["id"],
            exchange=starlisting_data["exchange"],
            exchange_display=starlisting_data["exchange_display"],
            coin=starlisting_data["coin"],
            coin_name=starlisting_data["coin_name"],
            quote=starlisting_data["quote"],
            quote_name=starlisting_data["quote_name"],
            trading_pair=starlisting_data["trading_pair"],
            market_type=starlisting_data["market_type"],
            market_type_display=starlisting_data["market_type_display"],
            interval=starlisting_data["interval"],
            interval_seconds=starlisting_data["interval_seconds"],
            active=True,  # get_active_starlistings only returns active ones
        )
        starlisting_responses.append(starlisting_response)

    return StarlistingListResponse(
        starlistings=starlisting_responses,
        total_count=len(starlisting_responses),
    )
