"""add_backfill_tracking_table

Revision ID: 33cd00d7748f
Revises: ef041ce476ce
Create Date: 2025-10-24 10:56:59.283816

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33cd00d7748f'
down_revision: Union[str, None] = 'ef041ce476ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create backfill_job table for tracking backfill progress
    op.create_table(
        'backfill_job',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('data_type', sa.String(50), nullable=False),  # 'candles', 'funding_rates', 'open_interest'
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # 'pending', 'running', 'completed', 'failed'
        sa.Column('records_fetched', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['listing_id'], ['listing.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('idx_backfill_job_listing', 'backfill_job', ['listing_id'])
    op.create_index('idx_backfill_job_status', 'backfill_job', ['status'])
    op.create_index('idx_backfill_job_data_type', 'backfill_job', ['data_type'])


def downgrade() -> None:
    op.drop_index('idx_backfill_job_data_type', table_name='backfill_job')
    op.drop_index('idx_backfill_job_status', table_name='backfill_job')
    op.drop_index('idx_backfill_job_listing', table_name='backfill_job')
    op.drop_table('backfill_job')
