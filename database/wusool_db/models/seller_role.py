"""`seller_roles` — real columns; see `003_crm_roles.sql`, amended in `004_machine_layer.sql`.

This table IS the seller's structured profile: there is no separate
`seller_profiles` table (PRD.md §3.3 describes a versioned one, but it was
never implemented — see the schema-gap note in the Phase 2 plan). One row
per organization (`UNIQUE(org_attio_id)`), no version column.

matching-engine and ddl-commands each had their own copy of this class before
Stage 1 of the Alembic migration (see `ALEMBIC_MIGRATION_HANDOVER.md`); they
differed only in `mandate_id` — matching-engine declared a real
`ForeignKey("mandates.id")` (matching-engine also maps `mandates`),
ddl-commands declared a plain column (it never mapped `mandates`). This is
matching-engine's version; ddl-commands never traverses a `mandate`
relationship here, so the FK object is a no-op for it.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class SellerRole(Base):
    __tablename__ = "seller_roles"
    __table_args__ = (Index("idx_seller_roles_intake_source", "intake_source"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    outreach_tier: Mapped[str | None] = mapped_column(Text)
    appetite_signal: Mapped[str | None] = mapped_column(Text)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    # Money shape confirmed from database/sync-postgres.ps1: {"amount": ..., "currency": ...}
    # or the column is NULL entirely — never fabricated when absent.
    est_revenue: Mapped[dict | None] = mapped_column(JSONB)
    est_ebitda: Mapped[dict | None] = mapped_column(JSONB)
    owner_salary: Mapped[dict | None] = mapped_column(JSONB)
    valuation_low: Mapped[dict | None] = mapped_column(JSONB)
    valuation_mid: Mapped[dict | None] = mapped_column(JSONB)
    valuation_high: Mapped[dict | None] = mapped_column(JSONB)
    sell_timeline: Mapped[str | None] = mapped_column(Text)
    readiness_score: Mapped[Decimal | None] = mapped_column(Numeric)
    readiness_band: Mapped[str | None] = mapped_column(Text)
    intake_source: Mapped[str | None] = mapped_column(Text)
    mandate_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("mandates.id"))
    last_attempt_date: Mapped[date | None] = mapped_column()
    last_attempt_channel: Mapped[str | None] = mapped_column(Text)
    last_attempt_outcome: Mapped[str | None] = mapped_column(Text)
    lead_quality_score: Mapped[Decimal | None] = mapped_column(Numeric)
    re_engage_date: Mapped[date | None] = mapped_column()
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization"] = relationship(back_populates="seller_role")
