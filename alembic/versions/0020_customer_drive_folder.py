"""Add drive_folder_id to customers table for Google Drive integration.

Each customer gets their own subfolder inside Customer-folder.
When a new customer is onboarded, the system creates:
  Uusio/Customer-folder/<Customer Name>/

Root Customer-folder ID: 1YI4bQu8cxtCYbfGcrA9KJyS6nO_xeVz3
Set as env var: DRIVE_CUSTOMER_ROOT_FOLDER_ID

Drive structure:
  Uusio/
  ├── Customer-folder/     (1YI4bQu8cxtCYbfGcrA9KJyS6nO_xeVz3)
  │   ├── <Customer A>/
  │   ├── <Customer B>/
  │   └── ...
  └── PRO Organisations/
      └── ...

Revision ID: 0020_customer_drive_folder
Revises: 0019_pro_drive_folder_ids
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_customer_drive_folder"
down_revision = "0019_pro_drive_folder_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-customer Drive folder — populated when customer folder is created via API
    op.add_column(
        "customers",
        sa.Column("drive_folder_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "drive_folder_id")
