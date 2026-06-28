"""Add chat_history table for persistent portal assistant memory.

Revision ID: 0012_add_chat_history
Revises: 0011_margin_15pct
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0012_add_chat_history"
down_revision = "0011_margin_15pct"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_history_customer_created",
                    "chat_history", ["customer_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_history_customer_created", table_name="chat_history")
    op.drop_table("chat_history")
