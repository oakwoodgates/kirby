"""add_funding_rates_and_open_interest_tables

Revision ID: 20c3c7f31fc7
Revises: 2ef4f41d558b
Create Date: 2025-11-01 20:05:03.263644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20c3c7f31fc7'
down_revision: Union[str, None] = '2ef4f41d558b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create funding_rates table
    op.create_table(
        'funding_rates',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('starlisting_id', sa.Integer(), nullable=False),

        # Core funding data
        sa.Column('funding_rate', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('premium', sa.Numeric(precision=20, scale=10), nullable=True),

        # Price context
        sa.Column('mark_price', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('index_price', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('oracle_price', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('mid_price', sa.Numeric(precision=20, scale=4), nullable=True),

        # Timing
        sa.Column('next_funding_time', sa.DateTime(timezone=True), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.ForeignKeyConstraint(['starlisting_id'], ['starlistings.id'], name=op.f('fk_funding_rates_starlisting_id_starlistings')),
        sa.PrimaryKeyConstraint('time', 'starlisting_id', name=op.f('pk_funding_rates'))
    )

    # Create indexes for funding_rates
    op.create_index('ix_funding_rates_starlisting_time', 'funding_rates', ['starlisting_id', 'time'], unique=False)
    op.create_index('ix_funding_rates_time', 'funding_rates', ['time'], unique=False, postgresql_using='brin')

    # Convert to hypertable using TimescaleDB
    op.execute("SELECT create_hypertable('funding_rates', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);")

    # Create open_interest table
    op.create_table(
        'open_interest',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('starlisting_id', sa.Integer(), nullable=False),

        # Open interest data
        sa.Column('open_interest', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('notional_value', sa.Numeric(precision=20, scale=4), nullable=True),

        # Volume context
        sa.Column('day_base_volume', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('day_notional_volume', sa.Numeric(precision=20, scale=4), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.ForeignKeyConstraint(['starlisting_id'], ['starlistings.id'], name=op.f('fk_open_interest_starlisting_id_starlistings')),
        sa.PrimaryKeyConstraint('time', 'starlisting_id', name=op.f('pk_open_interest'))
    )

    # Create indexes for open_interest
    op.create_index('ix_open_interest_starlisting_time', 'open_interest', ['starlisting_id', 'time'], unique=False)
    op.create_index('ix_open_interest_time', 'open_interest', ['time'], unique=False, postgresql_using='brin')

    # Convert to hypertable using TimescaleDB
    op.execute("SELECT create_hypertable('open_interest', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);")


def downgrade() -> None:
    # Drop indexes and tables for open_interest
    op.drop_index('ix_open_interest_time', table_name='open_interest', postgresql_using='brin')
    op.drop_index('ix_open_interest_starlisting_time', table_name='open_interest')
    op.drop_table('open_interest')

    # Drop indexes and tables for funding_rates
    op.drop_index('ix_funding_rates_time', table_name='funding_rates', postgresql_using='brin')
    op.drop_index('ix_funding_rates_starlisting_time', table_name='funding_rates')
    op.drop_table('funding_rates')
