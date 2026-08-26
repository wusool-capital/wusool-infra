"""`buyer_roles` — real columns; see `003_crm_roles.sql`.

This table IS the buyer's requirement profile: there is no separate
`buyer_requirement_profiles` table (PRD.md §3.3 describes one, but it was
never implemented — see the schema-gap note in the Phase 2 plan). One row
per organization (`UNIQUE(org_attio_id)`), no version column: this is flat,
unversioned data, not a version history.

matching-engine and ddl-commands each had their own copy of this class before
Stage 1 of the Alembic migration (see `ALEMBIC_MIGRATION_HANDOVER.md`);
they differed only in `key_contact_attio_id` — matching-engine declared it as
a real `ForeignKey("people.attio_id")` with a `key_contact` relationship
(matching-engine also maps `people`), ddl-commands declared it as a plain
column (ddl-commands never mapped `people`, so it couldn't reference it).
This is matching-engine's version — a real FK object here doesn't change any
behavior for ddl-commands (it never traverses `key_contact`), and this repo
maps `people` regardless.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization
    from wusool_db.models.person import Person


class BuyerRole(Base):
    __tablename__ = "buyer_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    model: Mapped[str | None] = mapped_column(Text)
    mandate_status: Mapped[str | None] = mapped_column(Text)
    # Money shape confirmed from database/sync-postgres.ps1: {"amount": ..., "currency": ...}
    # or the column is NULL entirely — never fabricated when absent.
    ebitda_floor: Mapped[dict | None] = mapped_column(JSONB)
    check_size_min: Mapped[dict | None] = mapped_column(JSONB)
    check_size_max: Mapped[dict | None] = mapped_column(JSONB)
    ev_ceiling: Mapped[dict | None] = mapped_column(JSONB)
    deal_structure_tolerance: Mapped[str | None] = mapped_column(Text)
    earnout_tolerance: Mapped[bool | None] = mapped_column()
    profitable_only: Mapped[bool | None] = mapped_column()
    investment_strategy: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    key_contact_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("people.attio_id"))
    acquisition_enrichment: Mapped[str | None] = mapped_column(Text)
    deals_introduced: Mapped[int | None] = mapped_column()
    deals_converted: Mapped[int | None] = mapped_column()
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact). `target_geography` is a real DEV
    # Attio multiselect — stored as an array of the selected option titles,
    # same pattern as `Organization.type`/`sector_focus`.
    ebitda_ceiling: Mapped[dict | None] = mapped_column(JSONB)
    estimated_aum: Mapped[dict | None] = mapped_column(JSONB)
    # mandate_details dropped 2026-08-23: redundant with investment_strategy
    # above -- same information, two places to maintain it. See
    # migration-decisions.json's dropped_fields.
    notable_investments: Mapped[str | None] = mapped_column(Text)
    key_personnel: Mapped[str | None] = mapped_column(Text)
    relationship_warmth: Mapped[str | None] = mapped_column(Text)
    target_geography: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    # typical_check_size dropped 2026-08-23: redundant with check_size_min/max
    # above -- it was a coarse 4-option USD range bucket, backfilled into
    # those two real USD figures rather than kept as its own column. See
    # migration-decisions.json's dropped_fields.
    last_mandate_briefing_date: Mapped[date | None] = mapped_column()
    prior_gcc_acquisition: Mapped[str | None] = mapped_column(Text)
    # Mirrors DEV Attio's Buyer Database is_active/legacy_entry_id (added
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

    organization: Mapped["Organization"] = relationship(back_populates="buyer_role")
    key_contact: Mapped["Person | None"] = relationship(foreign_keys=[key_contact_attio_id])
