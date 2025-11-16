"""increase numeric precision for all coins

Revision ID: increase_precision_001
Revises: 20c3c7f31fc7
Create Date: 2025-11-16 01:50:00.000000

Changes precision of all Numeric columns to support coins with very small prices
(e.g., meme coins at $0.000000001234) and very large volumes.

Before:
- Candle prices: Numeric(20, 8) - 8 decimals
- Funding prices: Numeric(20, 4) - 4 decimals (!)
- Volumes: Various

After:
- All prices: Numeric(30, 18) - 18 decimals
- All volumes: Numeric(40, 18) - 18 decimals
- All rates: Numeric(20, 18) - 18 decimals

This ensures no data loss for coins with prices ranging from $0.000000000000000001
to $999,999,999,999.99 and beyond.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC

# revision identifiers, used by Alembic.
revision: str = "increase_precision_001"
down_revision: Union[str, None] = "20c3c7f31fc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase precision of all Numeric columns."""

    # CANDLES TABLE
    # Change price columns from Numeric(20, 8) to Numeric(30, 18)
    op.alter_column(
        "candles",
        "open",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "high",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "low",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "close",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=False,
    )
    # Change volume from Numeric(30, 8) to Numeric(40, 18)
    op.alter_column(
        "candles",
        "volume",
        type_=NUMERIC(precision=40, scale=18),
        existing_type=NUMERIC(precision=30, scale=8),
        existing_nullable=False,
    )

    # FUNDING_RATES TABLE
    # Keep rates at high precision, but increase to 18 for consistency
    op.alter_column(
        "funding_rates",
        "funding_rate",
        type_=NUMERIC(precision=20, scale=18),
        existing_type=NUMERIC(precision=20, scale=10),
        existing_nullable=False,
    )
    op.alter_column(
        "funding_rates",
        "premium",
        type_=NUMERIC(precision=20, scale=18),
        existing_type=NUMERIC(precision=20, scale=10),
        existing_nullable=True,
    )

    # CRITICAL: Change price columns from Numeric(20, 4) to Numeric(30, 18)
    # 4 decimals is way too low for small-priced coins!
    op.alter_column(
        "funding_rates",
        "mark_price",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "index_price",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "oracle_price",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "mid_price",
        type_=NUMERIC(precision=30, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )

    # OPEN_INTEREST TABLE
    # Change from Numeric(20, 8) to Numeric(40, 18) for large volumes
    op.alter_column(
        "open_interest",
        "open_interest",
        type_=NUMERIC(precision=40, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=False,
    )
    # Change notional value from Numeric(20, 4) to Numeric(40, 18)
    op.alter_column(
        "open_interest",
        "notional_value",
        type_=NUMERIC(precision=40, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )
    # Change volume fields from Numeric(20, 8/4) to Numeric(40, 18)
    op.alter_column(
        "open_interest",
        "day_base_volume",
        type_=NUMERIC(precision=40, scale=18),
        existing_type=NUMERIC(precision=20, scale=8),
        existing_nullable=True,
    )
    op.alter_column(
        "open_interest",
        "day_notional_volume",
        type_=NUMERIC(precision=40, scale=18),
        existing_type=NUMERIC(precision=20, scale=4),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert precision changes (NOT RECOMMENDED - will lose precision)."""

    # WARNING: Downgrading will TRUNCATE data to lower precision!
    # Only use this if you understand the implications.

    # CANDLES TABLE
    op.alter_column(
        "candles",
        "open",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "high",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "low",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "close",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "candles",
        "volume",
        type_=NUMERIC(precision=30, scale=8),
        existing_type=NUMERIC(precision=40, scale=18),
        existing_nullable=False,
    )

    # FUNDING_RATES TABLE
    op.alter_column(
        "funding_rates",
        "funding_rate",
        type_=NUMERIC(precision=20, scale=10),
        existing_type=NUMERIC(precision=20, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "funding_rates",
        "premium",
        type_=NUMERIC(precision=20, scale=10),
        existing_type=NUMERIC(precision=20, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "mark_price",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "index_price",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "oracle_price",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "funding_rates",
        "mid_price",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=30, scale=18),
        existing_nullable=True,
    )

    # OPEN_INTEREST TABLE
    op.alter_column(
        "open_interest",
        "open_interest",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=40, scale=18),
        existing_nullable=False,
    )
    op.alter_column(
        "open_interest",
        "notional_value",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=40, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "open_interest",
        "day_base_volume",
        type_=NUMERIC(precision=20, scale=8),
        existing_type=NUMERIC(precision=40, scale=18),
        existing_nullable=True,
    )
    op.alter_column(
        "open_interest",
        "day_notional_volume",
        type_=NUMERIC(precision=20, scale=4),
        existing_type=NUMERIC(precision=40, scale=18),
        existing_nullable=True,
    )
