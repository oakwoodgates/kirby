"""Create trading_pairs table and add to starlistings

Revision ID: trading_pairs_001
Revises: auth_001
Create Date: 2025-11-19 00:00:00.000000

This migration creates a trading_pairs table to represent unique combinations
of (exchange, coin, quote_currency, market_type) independent of interval.

Funding rates and open interest are per trading pair, not per starlisting,
so this table provides the correct granularity for that data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'trading_pairs_001'
down_revision: Union[str, None] = 'auth_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trading_pairs table and populate from starlistings."""

    # Create trading_pairs table
    op.create_table(
        'trading_pairs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('exchange_id', sa.Integer(), nullable=False),
        sa.Column('coin_id', sa.Integer(), nullable=False),
        sa.Column('quote_currency_id', sa.Integer(), nullable=False),
        sa.Column('market_type_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(
            ['exchange_id'],
            ['exchanges.id'],
            name=op.f('fk_trading_pairs_exchange_id_exchanges')
        ),
        sa.ForeignKeyConstraint(
            ['coin_id'],
            ['coins.id'],
            name=op.f('fk_trading_pairs_coin_id_coins')
        ),
        sa.ForeignKeyConstraint(
            ['quote_currency_id'],
            ['quote_currencies.id'],
            name=op.f('fk_trading_pairs_quote_currency_id_quote_currencies')
        ),
        sa.ForeignKeyConstraint(
            ['market_type_id'],
            ['market_types.id'],
            name=op.f('fk_trading_pairs_market_type_id_market_types')
        ),

        # Primary key
        sa.PrimaryKeyConstraint('id', name=op.f('pk_trading_pairs')),

        # Unique constraint on the combination
        sa.UniqueConstraint(
            'exchange_id',
            'coin_id',
            'quote_currency_id',
            'market_type_id',
            name=op.f('uq_trading_pairs_exchange_coin_quote_market')
        )
    )

    # Create indexes for common lookup patterns
    op.create_index(
        'ix_trading_pairs_exchange_coin',
        'trading_pairs',
        ['exchange_id', 'coin_id'],
        unique=False
    )
    op.create_index(
        'ix_trading_pairs_coin',
        'trading_pairs',
        ['coin_id'],
        unique=False
    )

    # Populate trading_pairs from existing starlistings
    # Extract unique combinations of (exchange, coin, quote, market_type)
    op.execute("""
        INSERT INTO trading_pairs (exchange_id, coin_id, quote_currency_id, market_type_id)
        SELECT DISTINCT
            exchange_id,
            coin_id,
            quote_currency_id,
            market_type_id
        FROM starlistings
        ORDER BY exchange_id, coin_id, quote_currency_id, market_type_id
    """)

    # Add trading_pair_id column to starlistings (nullable initially)
    op.add_column(
        'starlistings',
        sa.Column('trading_pair_id', sa.Integer(), nullable=True)
    )

    # Populate trading_pair_id in starlistings
    # Match each starlisting to its corresponding trading pair
    op.execute("""
        UPDATE starlistings sl
        SET trading_pair_id = tp.id
        FROM trading_pairs tp
        WHERE sl.exchange_id = tp.exchange_id
          AND sl.coin_id = tp.coin_id
          AND sl.quote_currency_id = tp.quote_currency_id
          AND sl.market_type_id = tp.market_type_id
    """)

    # Make trading_pair_id NOT NULL after population
    op.alter_column(
        'starlistings',
        'trading_pair_id',
        nullable=False
    )

    # Add foreign key constraint
    op.create_foreign_key(
        op.f('fk_starlistings_trading_pair_id_trading_pairs'),
        'starlistings',
        'trading_pairs',
        ['trading_pair_id'],
        ['id']
    )

    # Create index on trading_pair_id for efficient joins
    op.create_index(
        'ix_starlistings_trading_pair',
        'starlistings',
        ['trading_pair_id'],
        unique=False
    )


def downgrade() -> None:
    """Drop trading_pairs table and remove from starlistings."""

    # Drop index from starlistings
    op.drop_index('ix_starlistings_trading_pair', table_name='starlistings')

    # Drop foreign key constraint
    op.drop_constraint(
        op.f('fk_starlistings_trading_pair_id_trading_pairs'),
        'starlistings',
        type_='foreignkey'
    )

    # Drop column from starlistings
    op.drop_column('starlistings', 'trading_pair_id')

    # Drop indexes from trading_pairs
    op.drop_index('ix_trading_pairs_coin', table_name='trading_pairs')
    op.drop_index('ix_trading_pairs_exchange_coin', table_name='trading_pairs')

    # Drop trading_pairs table
    op.drop_table('trading_pairs')
