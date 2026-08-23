"""`seller_roles` — real columns; see `003_crm_roles.sql`, amended in `004_machine_layer.sql`.

This table IS the seller's structured profile: there is no separate
`seller_profiles` table (PRD.md §3.3 describes a versioned one, but it was
never implemented — see the schema-gap note in the Phase 2 plan). One row
per organization (`UNIQUE(org_attio_id)`), no version column.

`mandate_id` (an FK to the now-dropped `mandates` table) was removed
2026-08-23 alongside `mandates`/`mandate_targets` themselves — the Mandates
list is fully retired, merged into Deal. See migration-decisions.json.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class SellerRole(Base):
    __tablename__ = "seller_roles"

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
    # mandate_id dropped 2026-08-23 alongside the mandates table itself --
    # the Mandates list is fully retired, merged into Deal. See
    # migration-decisions.json.
    last_attempt_date: Mapped[date | None] = mapped_column()
    last_attempt_channel: Mapped[str | None] = mapped_column(Text)
    last_attempt_outcome: Mapped[str | None] = mapped_column(Text)
    lead_quality_score: Mapped[Decimal | None] = mapped_column(Numeric)
    re_engage_date: Mapped[date | None] = mapped_column()
    # Mirrors DEV Attio's Seller Database is_active/legacy_entry_id (added
    # 2026-08-19 when duplicate SOURCE submissions were split into separate
    # DEV entries instead of being blended) — only ever the active entry
    # lands here since sync-postgres.ps1 filters on is_active before writing,
    # but legacy_entry_id still records which exact DEV entry this row came from.
    is_active: Mapped[bool | None] = mapped_column()
    legacy_entry_id: Mapped[str | None] = mapped_column(Text)
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization"] = relationship(back_populates="seller_role")
