"""`mandates` — real columns; see `002_core_attio_mirror.sql`.

`mandate_targets` is not mapped in this phase — no repository or test needs
it yet.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    attio_id: Mapped[str | None] = mapped_column(Text, unique=True)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    buyer_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    seller_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    phase: Mapped[str | None] = mapped_column(Text)
    assigned_advisor_attio_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    start_date: Mapped[date | None] = mapped_column()
    expiry_date: Mapped[date | None] = mapped_column()
    universe_constructed: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    shortlist_approved: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    universe_size: Mapped[int | None] = mapped_column()
    shortlist_size: Mapped[int | None] = mapped_column()
    tier1_contacted: Mapped[int | None] = mapped_column()
    responses: Mapped[int | None] = mapped_column()
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact). `retainer_amount` is DEV Attio type
    # "currency" (unlike SOURCE's plain-number `retainer_amount_aed`) — money
    # shape confirmed via database/sync-postgres.ps1's existing convention.
    sellers_interested: Mapped[int | None] = mapped_column(Integer)
    retainer_amount: Mapped[dict | None] = mapped_column(JSONB)
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[buyer_attio_id], back_populates="mandates_as_buyer"
    )
    seller_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[seller_attio_id], back_populates="mandates_as_seller"
    )
