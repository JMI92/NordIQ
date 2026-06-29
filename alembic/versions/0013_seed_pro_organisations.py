"""Seed initial PRO organisations from partner outreach responses.

Revision ID: 0013_seed_pro_orgs
Revises: 0012_add_chat_history
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_seed_pro_orgs"
down_revision = "0012_add_chat_history"
branch_labels = None
depends_on = None

PRO_DATA = [
    # Austria — WEEE + Batteries (UFH Holding GmbH)
    {
        "pro_key": "ufh-at-weee",
        "name": "UFH Holding GmbH",
        "country_code": "AT",
        "category": "weee",
        "website": "https://ufh.at/en",
        "contact_name": "Michael Hammer",
        "contact_email": "michael.hammer@ufh.at",
        "contact_phone": "+43 1 588 39-50",
        "submission_method": "portal",
        "submission_email": "office@ufh.at",
        "report_format": "portal_only",
        "notes": (
            "AR service for foreign producers and distance sellers. "
            "Annual minimum fee EUR 160 (excl. VAT). "
            "Quarterly reporting up to EUR 30k turnover, monthly above. "
            "Requires AR contract + notarized Power of Attorney (PoA) from each client. "
            "Registration via EDM-portal (Austrian ministry BMLUK). "
            "NDA required before detailed pricing is shared. "
            "Contact: michael.hammer@ufh.at"
        ),
        "reporting_deadline_notes": "Quarterly registration windows at the Austrian ministry.",
    },
    {
        "pro_key": "ufh-at-batteries",
        "name": "UFH Holding GmbH",
        "country_code": "AT",
        "category": "batteries",
        "website": "https://ufh.at/en",
        "contact_name": "Michael Hammer",
        "contact_email": "michael.hammer@ufh.at",
        "contact_phone": "+43 1 588 39-50",
        "submission_method": "portal",
        "submission_email": "office@ufh.at",
        "report_format": "portal_only",
        "notes": (
            "AR service for foreign producers and distance sellers — "
            "covers EU Battery Regulation (EU-BatterienVO) and Austrian Battery Ordinance (BATT-VO). "
            "Annual minimum fee EUR 160 (excl. VAT). "
            "Quarterly reporting up to EUR 30k, monthly above EUR 30k. "
            "Requires AR contract + notarized PoA from each client. "
            "Registration via EDM-portal. "
            "NDA required before detailed pricing is shared."
        ),
        "reporting_deadline_notes": "Quarterly registration windows at the Austrian ministry.",
    },
    # Spain — Batteries (ECOPILAS, managed by Recyclia)
    {
        "pro_key": "ecopilas-es",
        "name": "ECOPILAS",
        "country_code": "ES",
        "category": "batteries",
        "website": "https://www.recyclia.es",
        "portal_url": "https://www.raee-asimelec.es/adhesionfor_Ecopilas.asp",
        "contact_name": "Isabela Pedriel (Recyclia)",
        "contact_email": "ipedriel@recyclia.es",
        "contact_phone": "+34 91 417 08 90",
        "submission_method": "portal",
        "report_format": "portal_only",
        "notes": (
            "Collective scheme for batteries in Spain, administered by Recyclia. "
            "Joining fee EUR 300 (combined with ECOASIMELEC). "
            "Minimum quarterly fee EUR 125. "
            "Quarterly declarations in Jan, Apr, Jul, Oct — units and grams. "
            "Foreign companies without Spanish CIF need an Authorized Representative; "
            "Recyclia recommends OPEMED (contratos@recyclia.es). "
            "Fees depend on battery type, composition, and weight (see ECOPILAS 2025 fee schedule)."
        ),
        "reporting_deadline_notes": "Quarterly: January, April, July, October.",
    },
    # Spain — WEEE (ECOASIMELEC, managed by Recyclia)
    {
        "pro_key": "ecoasimelec-es",
        "name": "ECOASIMELEC",
        "country_code": "ES",
        "category": "weee",
        "website": "https://www.recyclia.es",
        "portal_url": "https://www.raee-asimelec.es/adhesionfor.asp",
        "contact_name": "Isabela Pedriel (Recyclia)",
        "contact_email": "ipedriel@recyclia.es",
        "contact_phone": "+34 91 417 08 90",
        "submission_method": "portal",
        "report_format": "portal_only",
        "notes": (
            "Collective scheme for WEEE in Spain, administered by Recyclia. "
            "Joining fee EUR 300 (combined with ECOPILAS). "
            "Minimum quarterly fee EUR 250. "
            "Quarterly declarations in units and kg per product category (7 categories per RD RAEE 110/2015). "
            "Foreign companies without Spanish CIF need an Authorized Representative; "
            "Recyclia recommends OPEMED (contratos@recyclia.es). "
            "Fees depend on product category (see FEES Ecoasimelec 2026 fee schedule)."
        ),
        "reporting_deadline_notes": "Quarterly: January, April, July, October.",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for pro in PRO_DATA:
        existing = conn.execute(
            sa.text("SELECT id FROM pro_organisations WHERE pro_key = :key"),
            {"key": pro["pro_key"]},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text("""
                INSERT INTO pro_organisations (
                    id, pro_key, name, country_code, category,
                    website, portal_url, contact_name, contact_email, contact_phone,
                    submission_method, submission_email, report_format,
                    notes, reporting_deadline_notes, is_active,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :pro_key, :name, :country_code, :category,
                    :website, :portal_url, :contact_name, :contact_email, :contact_phone,
                    :submission_method, :submission_email, :report_format,
                    :notes, :reporting_deadline_notes, true,
                    now(), now()
                )
            """),
            {
                "pro_key": pro["pro_key"],
                "name": pro["name"],
                "country_code": pro["country_code"],
                "category": pro["category"],
                "website": pro.get("website"),
                "portal_url": pro.get("portal_url"),
                "contact_name": pro.get("contact_name"),
                "contact_email": pro.get("contact_email"),
                "contact_phone": pro.get("contact_phone"),
                "submission_method": pro.get("submission_method"),
                "submission_email": pro.get("submission_email"),
                "report_format": pro.get("report_format", "generic_csv"),
                "notes": pro.get("notes"),
                "reporting_deadline_notes": pro.get("reporting_deadline_notes"),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [p["pro_key"] for p in PRO_DATA]
    conn.execute(
        sa.text("DELETE FROM pro_organisations WHERE pro_key = ANY(:keys)"),
        {"keys": keys},
    )
