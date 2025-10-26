"""Initial schema

Revision ID: 20251026_0001
Revises:
Create Date: 2025-10-26 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251026_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create exchanges table
    op.create_table(
        'exchanges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_exchanges')),
        sa.UniqueConstraint('name', name=op.f('uq_exchanges_name'))
    )
    op.create_index(op.f('ix_name'), 'exchanges', ['name'], unique=False)

    # Create coins table
    op.create_table(
        'coins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_coins')),
        sa.UniqueConstraint('symbol', name=op.f('uq_coins_symbol'))
    )
    op.create_index(op.f('ix_symbol'), 'coins', ['symbol'], unique=False)

    # Create market_types table
    op.create_table(
        'market_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_market_types')),
        sa.UniqueConstraint('name', name=op.f('uq_market_types_name'))
    )
    op.create_index(op.f('ix_name'), 'market_types', ['name'], unique=False)

    # Create intervals table
    op.create_table(
        'intervals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=10), nullable=False),
        sa.Column('seconds', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('seconds > 0', name=op.f('ck_intervals_positive_seconds')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_intervals')),
        sa.UniqueConstraint('name', name=op.f('uq_intervals_name'))
    )
    op.create_index(op.f('ix_name'), 'intervals', ['name'], unique=False)

    # Create starlistings table
    op.create_table(
        'starlistings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('exchange_id', sa.Integer(), nullable=False),
        sa.Column('coin_id', sa.Integer(), nullable=False),
        sa.Column('market_type_id', sa.Integer(), nullable=False),
        sa.Column('interval_id', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['coin_id'], ['coins.id'], name=op.f('fk_starlistings_coin_id_coins')),
        sa.ForeignKeyConstraint(['exchange_id'], ['exchanges.id'], name=op.f('fk_starlistings_exchange_id_exchanges')),
        sa.ForeignKeyConstraint(['interval_id'], ['intervals.id'], name=op.f('fk_starlistings_interval_id_intervals')),
        sa.ForeignKeyConstraint(['market_type_id'], ['market_types.id'], name=op.f('fk_starlistings_market_type_id_market_types')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_starlistings')),
        sa.UniqueConstraint('exchange_id', 'coin_id', 'market_type_id', 'interval_id', name=op.f('uq_starlisting'))
    )
    op.create_index('ix_starlisting_lookup', 'starlistings', ['exchange_id', 'coin_id', 'market_type_id', 'interval_id'], unique=False)

    # Create candles table
    op.create_table(
        'candles',
        sa.Column('time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('starlisting_id', sa.Integer(), nullable=False),
        sa.Column('open', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('high', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('low', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('close', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('volume', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('num_trades', sa.Integer(), nullable=True),
        sa.CheckConstraint('close > 0', name=op.f('ck_candles_positive_close')),
        sa.CheckConstraint('high > 0', name=op.f('ck_candles_positive_high')),
        sa.CheckConstraint('high >= close', name=op.f('ck_candles_valid_high_close')),
        sa.CheckConstraint('high >= low', name=op.f('ck_candles_valid_high_low')),
        sa.CheckConstraint('high >= open', name=op.f('ck_candles_valid_high_open')),
        sa.CheckConstraint('low <= close', name=op.f('ck_candles_valid_low_close')),
        sa.CheckConstraint('low <= open', name=op.f('ck_candles_valid_low_open')),
        sa.CheckConstraint('low > 0', name=op.f('ck_candles_positive_low')),
        sa.CheckConstraint('open > 0', name=op.f('ck_candles_positive_open')),
        sa.CheckConstraint('volume >= 0', name=op.f('ck_candles_non_negative_volume')),
        sa.ForeignKeyConstraint(['starlisting_id'], ['starlistings.id'], name=op.f('fk_candles_starlisting_id_starlistings')),
        sa.PrimaryKeyConstraint('time', 'starlisting_id', name=op.f('pk_candles'))
    )
    op.create_index('ix_candles_starlisting_time', 'candles', ['starlisting_id', 'time'], unique=False)
    op.create_index('ix_candles_time', 'candles', ['time'], unique=False, postgresql_using='brin')

    # Convert candles table to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable(
            'candles',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    """)

    # Seed data for intervals
    op.execute("""
        INSERT INTO intervals (name, seconds, active) VALUES
        ('1m', 60, true),
        ('3m', 180, true),
        ('5m', 300, true),
        ('15m', 900, true),
        ('30m', 1800, true),
        ('1h', 3600, true),
        ('2h', 7200, true),
        ('4h', 14400, true),
        ('8h', 28800, true),
        ('12h', 43200, true),
        ('1d', 86400, true),
        ('3d', 259200, true),
        ('1w', 604800, true);
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_candles_time', table_name='candles')
    op.drop_index('ix_candles_starlisting_time', table_name='candles')
    op.drop_table('candles')

    op.drop_index('ix_starlisting_lookup', table_name='starlistings')
    op.drop_table('starlistings')

    op.drop_index(op.f('ix_name'), table_name='intervals')
    op.drop_table('intervals')

    op.drop_index(op.f('ix_name'), table_name='market_types')
    op.drop_table('market_types')

    op.drop_index(op.f('ix_symbol'), table_name='coins')
    op.drop_table('coins')

    op.drop_index(op.f('ix_name'), table_name='exchanges')
    op.drop_table('exchanges')
