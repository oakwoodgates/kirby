"""add funding and oi notify triggers for websocket updates

Revision ID: funding_oi_notify_001
Revises: candle_notify_001
Create Date: 2025-11-17 10:00:00.000000

This migration adds PostgreSQL triggers and functions to emit NOTIFY events
when new funding rates or open interest records are inserted or updated.
This enables real-time WebSocket notifications to connected clients.

The triggers emit lightweight notifications with starlisting_id and timestamp,
allowing the WebSocket listener to query the full data efficiently.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "funding_oi_notify_001"
down_revision: Union[str, None] = "candle_notify_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add NOTIFY triggers for real-time funding rate and OI updates."""

    # Create trigger function for funding_rates table
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_funding_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Build JSON payload with minimal data (listener will query full record)
            payload := json_build_object(
                'starlisting_id', NEW.starlisting_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            -- Send notification on 'funding_updates' channel
            PERFORM pg_notify('funding_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on funding_rates table (fires AFTER INSERT or UPDATE)
    op.execute("""
        CREATE TRIGGER funding_update_notify_trigger
        AFTER INSERT OR UPDATE ON funding_rates
        FOR EACH ROW
        EXECUTE FUNCTION notify_funding_update();
    """)

    # Create trigger function for open_interest table
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_oi_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Build JSON payload with minimal data (listener will query full record)
            payload := json_build_object(
                'starlisting_id', NEW.starlisting_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            -- Send notification on 'oi_updates' channel
            PERFORM pg_notify('oi_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on open_interest table (fires AFTER INSERT or UPDATE)
    op.execute("""
        CREATE TRIGGER oi_update_notify_trigger
        AFTER INSERT OR UPDATE ON open_interest
        FOR EACH ROW
        EXECUTE FUNCTION notify_oi_update();
    """)


def downgrade() -> None:
    """Remove NOTIFY triggers and functions."""

    # Drop funding_rates trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS funding_update_notify_trigger ON funding_rates;
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS notify_funding_update();
    """)

    # Drop open_interest trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS oi_update_notify_trigger ON open_interest;
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS notify_oi_update();
    """)
