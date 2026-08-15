"""`seller_roles` — real columns; see `database/sql/003_crm_roles.sql`, amended
in `004_machine_layer.sql` and `008_bot_managed_columns.sql`.

One row per organization (`UNIQUE(org_attio_id)`), no version column.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base

if TYPE_CHECKING:
    from app.shared.database.models.organization import Organization


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
    readiness_score: Mapped[float | None] = mapped_column()
    readiness_band: Mapped[str | None] = mapped_column(Text)
    intake_source: Mapped[str | None] = mapped_column(Text)
    # Plain column, no FK relationship object — this bot doesn't traverse to
    # Mandate.
    mandate_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    last_attempt_date: Mapped[date | None] = mapped_column()
    last_attempt_channel: Mapped[str | None] = mapped_column(Text)
    last_attempt_outcome: Mapped[str | None] = mapped_column(Text)
    lead_quality_score: Mapped[float | None] = mapped_column()
    re_engage_date: Mapped[date | None] = mapped_column()
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # `008_bot_managed_columns.sql` — soft-delete + sync-collision-guard.
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    bot_managed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    bot_managed_by: Mapped[str | None] = mapped_column(Text)

    organization: Mapped["Organization"] = relationship(back_populates="seller_role")
