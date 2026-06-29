"""Add drive_folder_id to pro_organisations and seed Google Drive folder IDs.

Each PRO organisation gets its own Google Drive folder for storing
reports, contracts, and correspondence. Folder naming convention:
  <Country> - <Category> - <PRO name>

Drive structure:
  Uusio/
  └── PRO Organisations/       (19B7qyRnhcDv5E_7Ds63Yph9hXcV39QTW)
      ├── Austria - WEEE - UFH
      ├── Austria - Batteries - UFH
      ├── Spain - WEEE - ECOASIMELEC
      ├── Spain - Batteries - ECOPILAS
      ├── Netherlands - WEEE - Stichting OPEN
      └── Netherlands - Batteries - Stichting OPEN

Revision ID: 0019_pro_drive_folder_ids
Revises: 0018_ecopilas_fee_schedule
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_pro_drive_folder_ids"
down_revision = "0018_ecopilas_fee_schedule"
branch_labels = None
depends_on = None

# Parent folder: Uusio/PRO Organisations
PRO_ORGANISATIONS_FOLDER_ID = "19B7qyRnhcDv5E_7Ds63Yph9hXcV39QTW"

# Individual PRO folders inside PRO Organisations/
PRO_FOLDER_IDS = [
    ("ufh-at-weee",                 "1TpFwl6Omo7Ke34_no_frobUqn8ja3dKy"),  # Austria - WEEE - UFH
    ("ufh-at-batteries",            "1Efhsb68BExunyw6MN2LZb_9QPzJa8ksj"),  # Austria - Batteries - UFH
    ("ecoasimelec-es",              "1l1ZHYTfFOSugZz6ZjnuxDFogh8JsO-RT"),  # Spain - WEEE - ECOASIMELEC
    ("ecopilas-es",                 "1cqSsOVO1B2iPLPFsgQIG682_htgDraip"),   # Spain - Batteries - ECOPILAS
    ("stichting-open-nl-weee",      "1SeqrM7YiFp2zBENKYCFJQYlOMF0DxWjQ"),  # Netherlands - WEEE - Stichting OPEN
    ("stichting-open-nl-batteries", "1_aunpsM3uI-2CBY0gxhvuUlZk29AtHS2"),  # Netherlands - Batteries - Stichting OPEN
]


def upgrade() -> None:
    op.add_column(
        "pro_organisations",
        sa.Column("drive_folder_id", sa.String(100), nullable=True),
    )

    conn = op.get_bind()
    for pro_key, folder_id in PRO_FOLDER_IDS:
        conn.execute(
            sa.text(
                "UPDATE pro_organisations "
                "SET drive_folder_id = :folder_id, updated_at = now() "
                "WHERE pro_key = :pro_key"
            ),
            {"folder_id": folder_id, "pro_key": pro_key},
        )


def downgrade() -> None:
    op.drop_column("pro_organisations", "drive_folder_id")
