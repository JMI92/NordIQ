"""Initial schema — all core NordIQ tables.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # customers
    # ------------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vat_number", sa.String(50), nullable=True),
        sa.Column("country_of_incorporation", sa.String(2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customers_id", "customers", ["id"])
    op.create_index("ix_customers_vat_number", "customers", ["vat_number"])

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_customer_id", "users", ["customer_id"])

    # ------------------------------------------------------------------
    # customer_data_sources
    # ------------------------------------------------------------------
    op.create_table(
        "customer_data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("connection_config", sa.Text(), nullable=True),
        sa.Column("table_name", sa.String(500), nullable=True),
        sa.Column("field_mapping", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_data_sources_id", "customer_data_sources", ["id"])
    op.create_index("ix_customer_data_sources_customer_id", "customer_data_sources", ["customer_id"])

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_product_id", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("hs_code", sa.String(20), nullable=True),
        sa.Column("unit_of_measure", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("customer_id", "external_product_id", name="uq_product_customer_ext_id"),
    )
    op.create_index("ix_products_id", "products", ["id"])
    op.create_index("ix_products_customer_id", "products", ["customer_id"])
    op.create_index("ix_products_external_product_id", "products", ["external_product_id"])
    op.create_index("ix_products_product_category", "products", ["product_category"])

    # ------------------------------------------------------------------
    # product_weights
    # ------------------------------------------------------------------
    op.create_table(
        "product_weights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_weights_id", "product_weights", ["id"])
    op.create_index("ix_product_weights_customer_id", "product_weights", ["customer_id"])
    op.create_index("ix_product_weights_product_id", "product_weights", ["product_id"])
    op.create_index("ix_product_weights_material_type", "product_weights", ["material_type"])
    op.create_index("ix_product_weights_reporting_period_start", "product_weights", ["reporting_period_start"])
    op.create_index("ix_product_weights_reporting_period_end", "product_weights", ["reporting_period_end"])

    # ------------------------------------------------------------------
    # epr_rates
    # ------------------------------------------------------------------
    op.create_table(
        "epr_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("rate_per_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("regulation_reference", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "country_code", "product_category", "material_type", "valid_from",
            name="uq_epr_rate_country_category_material_from",
        ),
    )
    op.create_index("ix_epr_rates_id", "epr_rates", ["id"])
    op.create_index("ix_epr_rates_country_code", "epr_rates", ["country_code"])
    op.create_index("ix_epr_rates_product_category", "epr_rates", ["product_category"])
    op.create_index("ix_epr_rates_material_type", "epr_rates", ["material_type"])

    # ------------------------------------------------------------------
    # epr_obligations
    # ------------------------------------------------------------------
    op.create_table(
        "epr_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("pro_id", sa.String(100), nullable=False),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("total_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("fee_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_epr_obligations_id", "epr_obligations", ["id"])
    op.create_index("ix_epr_obligations_customer_id", "epr_obligations", ["customer_id"])
    op.create_index("ix_epr_obligations_country_code", "epr_obligations", ["country_code"])
    op.create_index("ix_epr_obligations_product_category", "epr_obligations", ["product_category"])
    op.create_index("ix_epr_obligations_status", "epr_obligations", ["status"])
    op.create_index("ix_epr_obligations_pro_id", "epr_obligations", ["pro_id"])

    # ------------------------------------------------------------------
    # pro_submissions
    # ------------------------------------------------------------------
    op.create_table(
        "pro_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("epr_obligations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pro_id", sa.String(100), nullable=False),
        sa.Column("submission_method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("report_file_path", sa.Text(), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pro_submissions_id", "pro_submissions", ["id"])
    op.create_index("ix_pro_submissions_customer_id", "pro_submissions", ["customer_id"])
    op.create_index("ix_pro_submissions_obligation_id", "pro_submissions", ["obligation_id"])
    op.create_index("ix_pro_submissions_pro_id", "pro_submissions", ["pro_id"])
    op.create_index("ix_pro_submissions_status", "pro_submissions", ["status"])

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_id", "audit_log", ["id"])
    op.create_index("ix_audit_log_customer_id", "audit_log", ["customer_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ------------------------------------------------------------------
    # import_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_data_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_jobs_id", "import_jobs", ["id"])
    op.create_index("ix_import_jobs_customer_id", "import_jobs", ["customer_id"])
    op.create_index("ix_import_jobs_data_source_id", "import_jobs", ["data_source_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # ------------------------------------------------------------------
    # reporting_deadlines
    # ------------------------------------------------------------------
    op.create_table(
        "reporting_deadlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("submission_deadline", sa.Date(), nullable=False),
        sa.Column("pro_id", sa.String(100), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "country_code", "product_category", "reporting_period_end",
            name="uq_deadline_country_category_period",
        ),
    )
    op.create_index("ix_reporting_deadlines_id", "reporting_deadlines", ["id"])
    op.create_index("ix_reporting_deadlines_country_code", "reporting_deadlines", ["country_code"])
    op.create_index("ix_reporting_deadlines_product_category", "reporting_deadlines", ["product_category"])
    op.create_index("ix_reporting_deadlines_submission_deadline", "reporting_deadlines", ["submission_deadline"])


def downgrade() -> None:
    op.drop_table("reporting_deadlines")
    op.drop_table("import_jobs")
    op.drop_table("audit_log")
    op.drop_table("pro_submissions")
    op.drop_table("epr_obligations")
    op.drop_table("epr_rates")
    op.drop_table("product_weights")
    op.drop_table("products")
    op.drop_table("customer_data_sources")
    op.drop_table("users")
    op.drop_table("customers")
