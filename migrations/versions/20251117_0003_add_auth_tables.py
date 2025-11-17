"""Add authentication tables for users and API keys.

Revision ID: auth_001
Revises: 20251102_0004_add_funding_oi_tables
Create Date: 2025-11-17 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "auth_001"
down_revision: Union[str, None] = "20251102_0004_add_funding_oi_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add users and api_keys tables."""

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),  # SHA-256 hash
        sa.Column("key_prefix", sa.String(length=10), nullable=False),  # First 8 chars for identification
        sa.Column("name", sa.String(length=100), nullable=True),  # Optional user-provided name
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("rate_limit", sa.Integer(), nullable=True),  # Requests per minute (NULL = use default)
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),  # NULL = never expires
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_api_keys_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_api_keys_key_hash")),
    )
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True)
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False)

    # Create api_key_usage table for logging
    op.create_table(
        "api_key_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),  # GET, POST, etc.
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),  # Response time in milliseconds
        sa.Column("ip_address", sa.String(length=45), nullable=True),  # IPv6 max length
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], name=op.f("fk_api_key_usage_api_key_id_api_keys"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_key_usage")),
    )
    op.create_index(op.f("ix_api_key_usage_api_key_id"), "api_key_usage", ["api_key_id"], unique=False)
    op.create_index(op.f("ix_api_key_usage_created_at"), "api_key_usage", ["created_at"], unique=False)

    # Create a TimescaleDB hypertable for api_key_usage (for efficient time-series queries)
    op.execute("SELECT create_hypertable('api_key_usage', 'created_at', if_not_exists => TRUE);")


def downgrade() -> None:
    """Remove authentication tables."""
    op.drop_table("api_key_usage")
    op.drop_table("api_keys")
    op.drop_table("users")
