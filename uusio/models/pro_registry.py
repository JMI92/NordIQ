"""PRO (Producer Responsibility Organisation) registry and customer registrations."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PROOrganisation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Producer Responsibility Organisation we work with."""

    __tablename__ = "pro_organisations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Country this PRO operates in, e.g. FI, SE, NO, DK, DE
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    # EPR category this PRO handles
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Internal short ID used in submissions (e.g. "rinki-fi", "el-kretsen-se")
    pro_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portal_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reporting_deadline_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Submission configuration — set per PRO during onboarding
    # Values: "email" | "api" | "portal" | "manual"
    submission_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    submission_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submission_api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submission_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Report format this PRO expects: "generic_csv" | "custom_csv" | "xml" | "portal_only"
    # Set once confirmed with the PRO; drives which generator auto_submitter uses
    report_format: Mapped[str] = mapped_column(String(20), nullable=False, default="generic_csv")
    # PRO-specific field mapping or XML schema config stored as JSON
    report_template_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    registrations: Mapped[list["CustomerPRORegistration"]] = relationship(
        "CustomerPRORegistration", back_populates="pro", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PROOrganisation {self.pro_key} ({self.country_code})>"


class CustomerPRORegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A customer's registration with a specific PRO in a specific country."""

    __tablename__ = "customer_pro_registrations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pro_organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Customer's own registration/member number at this PRO
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Material categories covered by this registration e.g. ["packaging", "electronics"]
    material_categories: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    # active / pending / expired / suspended
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    pro: Mapped["PROOrganisation"] = relationship("PROOrganisation", back_populates="registrations")
    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<CustomerPRORegistration customer={self.customer_id} pro={self.pro_id} [{self.status}]>"


class PROPortalCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Login credentials for a customer's account on a PRO's web portal.

    One row per CustomerPRORegistration that uses submission_method == "portal".
    The password is encrypted with the app Fernet key (uusio.core.security
    encrypt_config/decrypt_config), the same pattern already used for
    PROOrganisation.submission_api_key_encrypted.
    """

    __tablename__ = "pro_portal_credentials"

    customer_pro_registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_pro_registrations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    portal_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # active / invalid / locked — set to "invalid" automatically when login fails
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    registration: Mapped["CustomerPRORegistration"] = relationship("CustomerPRORegistration")

    def __repr__(self) -> str:
        return f"<PROPortalCredential registration={self.customer_pro_registration_id} [{self.status}]>"
