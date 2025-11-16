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

    # Use raw SQL for efficient batch column alterations
    # This avoids lock exhaustion on large tables by combining all changes into single statements

    # CANDLES TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE candles
        ALTER COLUMN open TYPE NUMERIC(30, 18),
        ALTER COLUMN high TYPE NUMERIC(30, 18),
        ALTER COLUMN low TYPE NUMERIC(30, 18),
        ALTER COLUMN close TYPE NUMERIC(30, 18),
        ALTER COLUMN volume TYPE NUMERIC(40, 18)
    """)

    # FUNDING_RATES TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE funding_rates
        ALTER COLUMN funding_rate TYPE NUMERIC(20, 18),
        ALTER COLUMN premium TYPE NUMERIC(20, 18),
        ALTER COLUMN mark_price TYPE NUMERIC(30, 18),
        ALTER COLUMN index_price TYPE NUMERIC(30, 18),
        ALTER COLUMN oracle_price TYPE NUMERIC(30, 18),
        ALTER COLUMN mid_price TYPE NUMERIC(30, 18)
    """)

    # OPEN_INTEREST TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE open_interest
        ALTER COLUMN open_interest TYPE NUMERIC(40, 18),
        ALTER COLUMN notional_value TYPE NUMERIC(40, 18),
        ALTER COLUMN day_base_volume TYPE NUMERIC(40, 18),
        ALTER COLUMN day_notional_volume TYPE NUMERIC(40, 18)
    """)


def downgrade() -> None:
    """Revert precision changes (NOT RECOMMENDED - will lose precision)."""

    # WARNING: Downgrading will TRUNCATE data to lower precision!
    # Only use this if you understand the implications.

    # Use raw SQL for efficient batch column alterations

    # CANDLES TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE candles
        ALTER COLUMN open TYPE NUMERIC(20, 8),
        ALTER COLUMN high TYPE NUMERIC(20, 8),
        ALTER COLUMN low TYPE NUMERIC(20, 8),
        ALTER COLUMN close TYPE NUMERIC(20, 8),
        ALTER COLUMN volume TYPE NUMERIC(30, 8)
    """)

    # FUNDING_RATES TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE funding_rates
        ALTER COLUMN funding_rate TYPE NUMERIC(20, 10),
        ALTER COLUMN premium TYPE NUMERIC(20, 10),
        ALTER COLUMN mark_price TYPE NUMERIC(20, 4),
        ALTER COLUMN index_price TYPE NUMERIC(20, 4),
        ALTER COLUMN oracle_price TYPE NUMERIC(20, 4),
        ALTER COLUMN mid_price TYPE NUMERIC(20, 4)
    """)

    # OPEN_INTEREST TABLE - all changes in one ALTER TABLE statement
    op.execute("""
        ALTER TABLE open_interest
        ALTER COLUMN open_interest TYPE NUMERIC(20, 8),
        ALTER COLUMN notional_value TYPE NUMERIC(20, 4),
        ALTER COLUMN day_base_volume TYPE NUMERIC(20, 8),
        ALTER COLUMN day_notional_volume TYPE NUMERIC(20, 4)
    """)
