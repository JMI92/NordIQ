"""Seed Stichting OPEN (Netherlands) PRO organisation.

Revision ID: 0015_seed_stichting_open
Revises: 0014_update_ufh_notes
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_seed_stichting_open"
down_revision = "0014_update_ufh_notes"
branch_labels = None
depends_on = None

PRO_DATA = [
    {
        "pro_key": "stichting-open-nl-weee",
        "name": "Stichting OPEN",
        "country_code": "NL",
        "category": "weee",
        "website": "https://www.stichting-open.org",
        "contact_name": "Arnoud Uri",
        "contact_email": "Producenten@stichting-open.org",
        "contact_phone": "+31 (0)79 7600 630",
        "submission_method": "portal",
        "report_format": "portal_only",
        "notes": (
            "MANDATORY and ONLY registry for WEEE producers and importers in the Netherlands — "
            "no alternative exists. Known from Wecycle brand. "
            "Companies can declare themselves or use a compliance agency as representative. "
            "Declarations made via participant account on their portal. "
            "Fee schedule: Waste-management-fee-EEE-2026 (see attachments). "
            "Compliance agency / API model not yet confirmed — follow up required."
        ),
        "reporting_deadline_notes": "Quarterly declarations via participant portal.",
    },
    {
        "pro_key": "stichting-open-nl-batteries",
        "name": "Stichting OPEN",
        "country_code": "NL",
        "category": "batteries",
        "website": "https://www.stichting-open.org",
        "contact_name": "Arnoud Uri",
        "contact_email": "Producenten@stichting-open.org",
        "contact_phone": "+31 (0)79 7600 630",
        "submission_method": "portal",
        "report_format": "portal_only",
        "notes": (
            "MANDATORY and ONLY registry for battery producers and importers in the Netherlands — "
            "no alternative exists. Known from Wecycle brand. "
            "Companies can declare themselves or use a compliance agency as representative. "
            "Declarations made via participant account on their portal. "
            "Fee schedule: Waste-management-fee-batteries-2026 (see attachments). "
            "Compliance agency / API model not yet confirmed — follow up required."
        ),
        "reporting_deadline_notes": "Quarterly declarations via participant portal.",
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
                    submission_method, report_format,
                    notes, reporting_deadline_notes, is_active,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :pro_key, :name, :country_code, :category,
                    :website, NULL, :contact_name, :contact_email, :contact_phone,
                    :submission_method, :report_format,
                    :notes, :reporting_deadline_notes, true,
                    now(), now()
                )
            """),
            {k: pro.get(k) for k in [
                "pro_key", "name", "country_code", "category",
                "website", "contact_name", "contact_email", "contact_phone",
                "submission_method", "report_format",
                "notes", "reporting_deadline_notes",
            ]},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [p["pro_key"] for p in PRO_DATA]
    conn.execute(
        sa.text("DELETE FROM pro_organisations WHERE pro_key = ANY(:keys)"),
        {"keys": keys},
    )
