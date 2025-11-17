"""add candle notify trigger for websocket updates

Revision ID: candle_notify_001
Revises: increase_precision_001
Create Date: 2025-11-17 00:01:00.000000

This migration adds a PostgreSQL trigger and function to emit NOTIFY events
when new candles are inserted or updated. This enables real-time WebSocket
notifications to connected clients without polling.

The trigger emits a lightweight notification with starlisting_id and timestamp,
allowing the WebSocket listener to query the full candle data efficiently.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "candle_notify_001"
down_revision: Union[str, None] = "increase_precision_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add NOTIFY trigger for real-time candle updates."""

    # Create trigger function that sends NOTIFY with lightweight payload
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_candle_update()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Build JSON payload with minimal data (listener will query full candle)
            payload := json_build_object(
                'starlisting_id', NEW.starlisting_id,
                'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
            )::TEXT;

            -- Send notification on 'candle_updates' channel
            PERFORM pg_notify('candle_updates', payload);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on candles table (fires AFTER INSERT or UPDATE)
    op.execute("""
        CREATE TRIGGER candle_update_notify_trigger
        AFTER INSERT OR UPDATE ON candles
        FOR EACH ROW
        EXECUTE FUNCTION notify_candle_update();
    """)


def downgrade() -> None:
    """Remove NOTIFY trigger and function."""

    # Drop trigger first (depends on function)
    op.execute("""
        DROP TRIGGER IF EXISTS candle_update_notify_trigger ON candles;
    """)

    # Drop trigger function
    op.execute("""
        DROP FUNCTION IF EXISTS notify_candle_update();
    """)
