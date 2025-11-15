"""
Database helper utilities for cross-database operations.

This module provides helper functions that work across both production
and training databases, with smart defaults and clear error messages.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Coin, Exchange, MarketType, QuoteCurrency, Starlisting


async def get_starlisting_params(
    session: AsyncSession,
    coin: str,
    exchange: str | None = None,
    quote: str | None = None,
    market_type: str | None = None,
) -> tuple[str, str, str]:
    """
    Resolve starlisting parameters by querying the database.

    This function queries the database for available starlistings matching
    the given coin, and intelligently resolves exchange, quote, and market_type
    parameters based on what's available.

    Auto-selection logic:
    - If only one option exists for a parameter, auto-select it
    - If multiple options exist, require explicit parameter
    - If no options exist, raise error

    Args:
        session: SQLAlchemy async session
        coin: Coin symbol (e.g., "BTC", "ETH")
        exchange: Optional exchange name (e.g., "hyperliquid", "binance")
        quote: Optional quote currency (e.g., "USD", "USDT")
        market_type: Optional market type (e.g., "perps", "spot")

    Returns:
        Tuple of (exchange, quote, market_type) - all resolved to actual values

    Raises:
        ValueError: If parameters are ambiguous or no matching starlistings found

    Examples:
        >>> # Auto-select when unambiguous
        >>> exchange, quote, market = await get_starlisting_params(session, "BTC")
        >>> # Returns ("hyperliquid", "USD", "perps") if only one combo exists
        >>>
        >>> # Explicit override
        >>> exchange, quote, market = await get_starlisting_params(
        ...     session, "BTC", exchange="binance", quote="USDT", market_type="perps"
        ... )
    """
    # Build query for active starlistings matching the coin
    query = (
        select(
            Exchange.name.label("exchange"),
            QuoteCurrency.symbol.label("quote"),
            MarketType.name.label("market_type"),
        )
        .select_from(Starlisting)
        .join(Coin, Starlisting.coin_id == Coin.id)
        .join(Exchange, Starlisting.exchange_id == Exchange.id)
        .join(QuoteCurrency, Starlisting.quote_currency_id == QuoteCurrency.id)
        .join(MarketType, Starlisting.market_type_id == MarketType.id)
        .where(Coin.symbol == coin.upper())
        .where(Starlisting.active == True)
        .distinct()
    )

    # Apply filters if parameters provided
    if exchange:
        query = query.where(Exchange.name == exchange.lower())
    if quote:
        query = query.where(QuoteCurrency.symbol == quote.upper())
    if market_type:
        query = query.where(MarketType.name == market_type.lower())

    result = await session.execute(query)
    rows = result.all()

    if not rows:
        # Build helpful error message
        filters = []
        if exchange:
            filters.append(f"exchange={exchange}")
        if quote:
            filters.append(f"quote={quote}")
        if market_type:
            filters.append(f"market_type={market_type}")

        filter_str = ", ".join(filters) if filters else "no filters"
        raise ValueError(
            f"No active starlistings found for coin '{coin}' with {filter_str}. "
            f"Check your database or adjust parameters."
        )

    # Extract unique values for each parameter
    exchanges = sorted({row.exchange for row in rows})
    quotes = sorted({row.quote for row in rows})
    market_types = sorted({row.market_type for row in rows})

    # Resolve exchange
    if not exchange:
        if len(exchanges) == 1:
            exchange = exchanges[0]
        else:
            raise ValueError(
                f"Coin '{coin}' has multiple exchanges: {', '.join(exchanges)}. "
                f"Please specify --exchange"
            )

    # Resolve quote
    if not quote:
        if len(quotes) == 1:
            quote = quotes[0]
        else:
            raise ValueError(
                f"Coin '{coin}' has multiple quote currencies: {', '.join(quotes)}. "
                f"Please specify --quote"
            )

    # Resolve market_type
    if not market_type:
        if len(market_types) == 1:
            market_type = market_types[0]
        else:
            raise ValueError(
                f"Coin '{coin}' has multiple market types: {', '.join(market_types)}. "
                f"Please specify --market-type"
            )

    return (exchange, quote, market_type)
