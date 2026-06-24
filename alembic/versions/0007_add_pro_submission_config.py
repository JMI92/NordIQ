"""Add PRO submission configuration fields to pro_organisations

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PRO submission method and contact config
    op.add_column("pro_organisations", sa.Column("submission_method", sa.String(20), nullable=True))
    op.add_column("pro_organisations", sa.Column("submission_email", sa.String(255), nullable=True))
    op.add_column("pro_organisations", sa.Column("submission_api_url", sa.String(500), nullable=True))
    op.add_column("pro_organisations", sa.Column("submission_api_key_encrypted", sa.Text, nullable=True))
    op.add_column("pro_organisations", sa.Column("submission_notes", sa.Text, nullable=True))

    # Import jobs — add filename column for tracking uploaded files
    op.add_column("import_jobs", sa.Column("original_filename", sa.String(500), nullable=True))
    op.add_column("import_jobs", sa.Column("ai_notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("pro_organisations", "submission_notes")
    op.drop_column("pro_organisations", "submission_api_key_encrypted")
    op.drop_column("pro_organisations", "submission_api_url")
    op.drop_column("pro_organisations", "submission_email")
    op.drop_column("pro_organisations", "submission_method")
    op.drop_column("import_jobs", "ai_notes")
    op.drop_column("import_jobs", "original_filename")
