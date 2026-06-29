"""Update UFH Austria PRO notes with additional importer list requirements.

Revision ID: 0014_update_ufh_notes
Revises: 0013_seed_pro_orgs
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_update_ufh_notes"
down_revision = "0013_seed_pro_orgs"
branch_labels = None
depends_on = None

UFH_NOTES = {
    "ufh-at-weee": (
        "AR service for foreign producers and distance sellers. "
        "Annual minimum fee EUR 160 (excl. VAT). "
        "Quarterly reporting up to EUR 30k turnover, monthly above. "
        "Requires AR contract + notarized Power of Attorney (PoA) from each client. "
        "Registration via EDM-portal (Austrian ministry BMLUK). "
        "NDA required before detailed pricing is shared. "
        "Contact: michael.hammer@ufh.at | "
        "ADDITIONAL REQUIREMENTS FOR FOREIGN PRODUCERS: "
        "(1) Prior to registration: must provide a list of Austrian importers (name, postal + email address) "
        "to whom electrical equipment is distributed — UFH forwards this to importers and BMLUK. "
        "(2) Annually: updated importer list with quantities (pieces/kg) distributed to each importer."
    ),
    "ufh-at-batteries": (
        "AR service for foreign producers and distance sellers — "
        "covers EU Battery Regulation (EU-BatterienVO) and Austrian Battery Ordinance (BATT-VO). "
        "Annual minimum fee EUR 160 (excl. VAT). "
        "Quarterly reporting up to EUR 30k, monthly above EUR 30k. "
        "Requires AR contract + notarized PoA from each client. "
        "Registration via EDM-portal. "
        "NDA required before detailed pricing is shared. "
        "ADDITIONAL REQUIREMENTS FOR FOREIGN PRODUCERS: "
        "(1) Prior to registration: must provide a list of Austrian importers (name, postal + email address) "
        "to whom batteries are distributed — UFH forwards this to importers and BMLUK. "
        "(2) Annually: updated importer list with quantities (pieces/kg) distributed to each importer."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    for pro_key, notes in UFH_NOTES.items():
        conn.execute(
            sa.text(
                "UPDATE pro_organisations SET notes = :notes, updated_at = now() "
                "WHERE pro_key = :pro_key"
            ),
            {"notes": notes, "pro_key": pro_key},
        )


def downgrade() -> None:
    pass
