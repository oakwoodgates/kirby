"""Migrate funding_rates and open_interest to use trading_pair_id

Revision ID: trading_pairs_002
Revises: trading_pairs_001
Create Date: 2025-11-19 00:01:00.000000

This migration updates the funding_rates and open_interest tables to reference
trading_pair_id instead of starlisting_id, since funding and OI data are per
trading pair (exchange + coin + quote + market_type), not per interval.

This is a breaking change that requires:
1. Dropping existing NOTIFY triggers (they reference starlisting_id)
2. Adding trading_pair_id column
3. Populating from starlistings
4. Changing primary key
5. Dropping starlisting_id column
6. Recreating triggers with trading_pair_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'trading_pairs_002'
down_revision: Union[str, None] = 'trading_pairs_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate funding_rates and open_interest to use trading_pair_id."""

    # ============================================================================
    # STEP 1: Drop existing NOTIFY triggers (they reference starlisting_id)
    # ============================================================================
    op.execute("""
        DROP TRIGGER IF EXISTS funding_update_notify_trigger ON funding_rates;
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS oi_update_notify_trigger ON open_interest;
    """)

    # ============================================================================
    # STEP 2: Migrate funding_rates table
    # ============================================================================

    # Add trading_pair_id column (nullable initially)
    op.add_column(
        'funding_rates',
        sa.Column('trading_pair_id', sa.Integer(), nullable=True)
    )

    # Populate trading_pair_id from starlistings
    op.execute("""
        UPDATE funding_rates fr
        SET trading_pair_id = sl.trading_pair_id
        FROM starlistings sl
        WHERE fr.starlisting_id = sl.id
    """)

    # Make trading_pair_id NOT NULL after population
    op.alter_column(
        'funding_rates',
        'trading_pair_id',
        nullable=False
    )

    # Drop old indexes that use starlisting_id
    op.drop_index('ix_funding_rates_starlisting_time', table_name='funding_rates')

    # Drop old primary key constraint
    op.drop_constraint('pk_funding_rates', 'funding_rates', type_='primary')

    # Create new primary key with trading_pair_id
    op.create_primary_key(
        'pk_funding_rates',
        'funding_rates',
        ['time', 'trading_pair_id']
    )

    # Drop old foreign key constraint
    op.drop_constraint(
        'fk_funding_rates_starlisting_id_starlistings',
        'funding_rates',
        type_='foreignkey'
    )

    # Drop starlisting_id column
    op.drop_column('funding_rates', 'starlisting_id')

    # Add new foreign key constraint for trading_pair_id
    op.create_foreign_key(
        op.f('fk_funding_rates_trading_pair_id_trading_pairs'),
        'funding_rates',
        'trading_pairs',
        ['trading_pair_id'],
        ['id']
    )

    # Create new index on trading_pair_id
    op.create_index(
        'ix_funding_rates_trading_pair_time',
        'funding_rates',
        ['trading_pair_id', 'time'],
        unique=False,
        postgresql_ops={'time': 'DESC'}
    )

    # ============================================================================
    # STEP 3: Migrate open_interest table
    # ============================================================================

    # Add trading_pair_id column (nullable initially)
    op.add_column(
        'open_interest',
        sa.Column('trading_pair_id', sa.Integer(), nullable=True)
    )

    # Populate trading_pair_id from starlistings
    op.execute("""
        UPDATE open_interest oi
        SET trading_pair_id = sl.trading_pair_id
        FROM starlistings sl
        WHERE oi.starlisting_id = sl.id
    """)

    # Make trading_pair_id NOT NULL after population
    op.alter_column(
        'open_interest',
        'trading_pair_id',
        nullable=False
    )

    # Drop old indexes that use starlisting_id
    op.drop_index('ix_open_interest_starlisting_time', table_name='open_interest')

    # Drop old primary key constraint
    op.drop_constraint('pk_open_interest', 'open_interest', type_='primary')

    # Create new primary key with trading_pair_id
    op.create_primary_key(
        'pk_open_interest',
        'open_interest',
        ['time', 'trading_pair_id']
    )

    # Drop old foreign key constraint
    op.drop_constraint(
        'fk_open_interest_starlisting_id_starlistings',
        'open_interest',
        type_='foreignkey'
    )

    # Drop starlisting_id column
    op.drop_column('open_interest', 'starlisting_id')

    # Add new foreign key constraint for trading_pair_id
    op.create_foreign_key(
        op.f('fk_open_interest_trading_pair_id_trading_pairs'),
        'open_interest',
        'trading_pairs',
        ['trading_pair_id'],
        ['id']
    )

    # Create new index on trading_pair_id
    op.create_index(
        'ix_open_interest_trading_pair_time',
        'open_interest',
        ['trading_pair_id', 'time'],
        unique=False,
        postgresql_ops={'time': 'DESC'}
    )

    # ============================================================================
    # STEP 4: Recreate NOTIFY triggers with trading_pair_id
    # ============================================================================

    # Create trigger function for funding_rates table (using trading_pair_id)
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_funding_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Build JSON payload with trading_pair_id instead of starlisting_id
            payload := json_build_object(
                'trading_pair_id', NEW.trading_pair_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            -- Send notification on 'funding_updates' channel
            PERFORM pg_notify('funding_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on funding_rates table
    op.execute("""
        CREATE TRIGGER funding_update_notify_trigger
        AFTER INSERT OR UPDATE ON funding_rates
        FOR EACH ROW
        EXECUTE FUNCTION notify_funding_update();
    """)

    # Create trigger function for open_interest table (using trading_pair_id)
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_oi_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Build JSON payload with trading_pair_id instead of starlisting_id
            payload := json_build_object(
                'trading_pair_id', NEW.trading_pair_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            -- Send notification on 'oi_updates' channel
            PERFORM pg_notify('oi_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on open_interest table
    op.execute("""
        CREATE TRIGGER oi_update_notify_trigger
        AFTER INSERT OR UPDATE ON open_interest
        FOR EACH ROW
        EXECUTE FUNCTION notify_oi_update();
    """)


def downgrade() -> None:
    """Revert funding_rates and open_interest back to starlisting_id."""

    # ============================================================================
    # STEP 1: Drop NOTIFY triggers (they use trading_pair_id)
    # ============================================================================
    op.execute("""
        DROP TRIGGER IF EXISTS funding_update_notify_trigger ON funding_rates;
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS oi_update_notify_trigger ON open_interest;
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS notify_funding_update();
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS notify_oi_update();
    """)

    # ============================================================================
    # STEP 2: Revert funding_rates table
    # ============================================================================

    # Add starlisting_id column back (nullable initially)
    op.add_column(
        'funding_rates',
        sa.Column('starlisting_id', sa.Integer(), nullable=True)
    )

    # Populate starlisting_id from trading_pairs
    # Choose the first starlisting for each trading pair (matches old behavior)
    op.execute("""
        UPDATE funding_rates fr
        SET starlisting_id = (
            SELECT MIN(sl.id)
            FROM starlistings sl
            WHERE sl.trading_pair_id = fr.trading_pair_id
        )
    """)

    # Make starlisting_id NOT NULL
    op.alter_column(
        'funding_rates',
        'starlisting_id',
        nullable=False
    )

    # Drop new indexes
    op.drop_index('ix_funding_rates_trading_pair_time', table_name='funding_rates')

    # Drop new primary key
    op.drop_constraint('pk_funding_rates', 'funding_rates', type_='primary')

    # Create old primary key
    op.create_primary_key(
        'pk_funding_rates',
        'funding_rates',
        ['time', 'starlisting_id']
    )

    # Drop new foreign key
    op.drop_constraint(
        op.f('fk_funding_rates_trading_pair_id_trading_pairs'),
        'funding_rates',
        type_='foreignkey'
    )

    # Drop trading_pair_id column
    op.drop_column('funding_rates', 'trading_pair_id')

    # Add old foreign key back
    op.create_foreign_key(
        'fk_funding_rates_starlisting_id_starlistings',
        'funding_rates',
        'starlistings',
        ['starlisting_id'],
        ['id']
    )

    # Recreate old index
    op.create_index(
        'ix_funding_rates_starlisting_time',
        'funding_rates',
        ['starlisting_id', 'time'],
        unique=False
    )

    # ============================================================================
    # STEP 3: Revert open_interest table
    # ============================================================================

    # Add starlisting_id column back (nullable initially)
    op.add_column(
        'open_interest',
        sa.Column('starlisting_id', sa.Integer(), nullable=True)
    )

    # Populate starlisting_id from trading_pairs
    op.execute("""
        UPDATE open_interest oi
        SET starlisting_id = (
            SELECT MIN(sl.id)
            FROM starlistings sl
            WHERE sl.trading_pair_id = oi.trading_pair_id
        )
    """)

    # Make starlisting_id NOT NULL
    op.alter_column(
        'open_interest',
        'starlisting_id',
        nullable=False
    )

    # Drop new indexes
    op.drop_index('ix_open_interest_trading_pair_time', table_name='open_interest')

    # Drop new primary key
    op.drop_constraint('pk_open_interest', 'open_interest', type_='primary')

    # Create old primary key
    op.create_primary_key(
        'pk_open_interest',
        'open_interest',
        ['time', 'starlisting_id']
    )

    # Drop new foreign key
    op.drop_constraint(
        op.f('fk_open_interest_trading_pair_id_trading_pairs'),
        'open_interest',
        type_='foreignkey'
    )

    # Drop trading_pair_id column
    op.drop_column('open_interest', 'trading_pair_id')

    # Add old foreign key back
    op.create_foreign_key(
        'fk_open_interest_starlisting_id_starlistings',
        'open_interest',
        'starlistings',
        ['starlisting_id'],
        ['id']
    )

    # Recreate old index
    op.create_index(
        'ix_open_interest_starlisting_time',
        'open_interest',
        ['starlisting_id', 'time'],
        unique=False
    )

    # ============================================================================
    # STEP 4: Recreate old NOTIFY triggers with starlisting_id
    # ============================================================================

    # Create old trigger function for funding_rates
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_funding_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            payload := json_build_object(
                'starlisting_id', NEW.starlisting_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            PERFORM pg_notify('funding_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER funding_update_notify_trigger
        AFTER INSERT OR UPDATE ON funding_rates
        FOR EACH ROW
        EXECUTE FUNCTION notify_funding_update();
    """)

    # Create old trigger function for open_interest
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_oi_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            payload := json_build_object(
                'starlisting_id', NEW.starlisting_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            PERFORM pg_notify('oi_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER oi_update_notify_trigger
        AFTER INSERT OR UPDATE ON open_interest
        FOR EACH ROW
        EXECUTE FUNCTION notify_oi_update();
    """)
