"""Add drive_folder_id to customers table for Google Drive integration.

Each customer gets their own subfolder inside Customer-folder.
When a new customer is onboarded, the system creates:
  Uusio/Customer-folder/<Customer Name>/

The root Customer-folder ID is stored in a config table / env var,
but also recorded here for reference.

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

# Root folder for all customer subfolders
CUSTOMER_FOLDER_ID = "1YI4bQu8cxtCYbfGcrA9KJyS6nO_xeVz3"


def upgrade() -> None:
    # Per-customer Drive folder — populated when customer folder is created
    op.add_column(
        "customers",
        sa.Column("drive_folder_id", sa.String(100), nullable=True),
    )

    # Store the root Customer-folder ID as a system config entry
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO system_config (key, value, updated_at)
            VALUES ('drive_customer_root_folder_id', :val, now())
            ON CONFLICT (key) DO UPDATE
              SET value = EXCLUDED.value, updated_at = now()
            """
        ),
        {"val": CUSTOMER_FOLDER_ID},
    )


def downgrade() -> None:
    op.drop_column("customers", "drive_folder_id")
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM system_config WHERE key = 'drive_customer_root_folder_id'")
    )
