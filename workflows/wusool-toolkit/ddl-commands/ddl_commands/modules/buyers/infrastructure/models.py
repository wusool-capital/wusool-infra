"""`buyer_roles` — real columns; see `database/sql/003_crm_roles.sql`, amended
in `004_machine_layer.sql`.

One row per organization (`UNIQUE(org_attio_id)`), no version column: this is
flat, unversioned data, not a version history.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ddl_commands.shared.database.base import Base

if TYPE_CHECKING:
    from ddl_commands.shared.database.models.organization import Organization


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
    earnout_tolerance: Mapped[str | None] = mapped_column(Text)
    profitable_only: Mapped[bool | None] = mapped_column()
    investment_strategy: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Plain column, no FK relationship object — this bot never displays/edits
    # the linked Person, so there's no need to map `people` here at all.
    key_contact_attio_id: Mapped[str | None] = mapped_column(Text)
    acquisition_enrichment: Mapped[str | None] = mapped_column(Text)
    deals_introduced: Mapped[int | None] = mapped_column()
    deals_converted: Mapped[int | None] = mapped_column()
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization"] = relationship(back_populates="buyer_role")
