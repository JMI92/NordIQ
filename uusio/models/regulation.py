"""EPR regulation library entry."""

from datetime import date

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from uusio.core.database import Base
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RegulationEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single regulation or statutory requirement in the EPR library."""

    __tablename__ = "regulation_entries"

    # e.g. FI, SE, NO, DK, DE, FR — or 'EU' for EU-wide
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    # e.g. Packaging, Electronics, Batteries, Textiles
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # ["PPWR", "SUP", "take-back", ...]
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<RegulationEntry {self.country_code}/{self.category}: {self.title[:40]}>"
