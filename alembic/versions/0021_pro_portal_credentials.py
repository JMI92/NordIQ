"""Add pro_portal_credentials table and submission failure-tracking columns.

Supports automated PRO portal submissions (Playwright-based):
  - pro_portal_credentials stores per customer+PRO login credentials,
    password encrypted with the app Fernet key (same pattern as
    PROOrganisation.submission_api_key_encrypted).
  - pro_submissions gains screenshot_s3_key (debug evidence of the last
    automation run) and needs_attention (set when retries are exhausted
    so an admin can see it without scanning every FAILED row).

Revision ID: 0021_pro_portal_credentials
Revises: 0020_customer_drive_folder
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_pro_portal_credentials"
down_revision = "0020_customer_drive_folder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pro_portal_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_pro_registration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_pro_registrations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("portal_url", sa.String(500), nullable=True),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("pro_submissions", sa.Column("screenshot_s3_key", sa.String(500), nullable=True))
    op.add_column(
        "pro_submissions",
        sa.Column("needs_attention", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pro_submissions", "needs_attention")
    op.drop_column("pro_submissions", "screenshot_s3_key")
    op.drop_table("pro_portal_credentials")
