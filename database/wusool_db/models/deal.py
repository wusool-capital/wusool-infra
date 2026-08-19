"""`deals` — real columns as they exist post-004 rename (`contract_signed_date`,
`exclusivity_date`; the old `exclusivity_start_date`/`_end_date` names are gone).

`deal_stage_events` is not mapped in this phase — no repository or test needs
it yet; add it later against the same pattern once something reads it.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Interval,
    Numeric,
    Text,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization
    from wusool_db.models.person import Person


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint(
            "buyer_organization_attio_id IS NULL OR buyer_person_attio_id IS NULL",
            name="deals_one_buyer",
        ),
        Index("idx_deals_buyer_org", "buyer_organization_attio_id"),
        Index("idx_deals_seller_org", "seller_organization_attio_id"),
        Index("idx_deals_stage", "stage"),
        Index("idx_deals_stage_changed_at", literal_column("stage_changed_at DESC")),
    )

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str | None] = mapped_column(Text)
    stage_changed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    buyer_organization_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id")
    )
    buyer_person_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("people.attio_id"))
    seller_organization_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id")
    )
    owner_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.attio_id", name="deals_owner_attio_id_fkey")
    )
    value: Mapped[dict | None] = mapped_column(JSONB)
    teaser_status: Mapped[str | None] = mapped_column(Text)
    nda_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # NOT NULL/DEFAULT were dropped from both in 004_machine_layer.sql — real NULLs exist.
    cim_ready: Mapped[bool | None] = mapped_column()
    deal_memo_ready: Mapped[bool | None] = mapped_column()
    contract_signed_date: Mapped[date | None] = mapped_column()
    exclusivity_date: Mapped[date | None] = mapped_column()
    next_task: Mapped[str | None] = mapped_column(Text)
    data_room_substatus: Mapped[str | None] = mapped_column(Text)
    comparables: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact). `estimated_deal_value_aed` and `fee`
    # are real DEV Attio type "number" (plain scalar), not "currency" — no
    # money-shape wrapping, unlike `value` above. `assigned_advisor` is a
    # plain multiselect of advisor names, not a workspace-member/User FK.
    nda_status: Mapped[str | None] = mapped_column(Text)
    estimated_deal_value_aed: Mapped[Decimal | None] = mapped_column(Numeric)
    expected_close_date: Mapped[date | None] = mapped_column()
    fee: Mapped[Decimal | None] = mapped_column(Numeric)
    assigned_advisor: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    time_in_stage: Mapped[timedelta | None] = mapped_column(Interval)

    buyer_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[buyer_organization_attio_id], back_populates="deals_as_buyer"
    )
    seller_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[seller_organization_attio_id], back_populates="deals_as_seller"
    )
    buyer_person: Mapped["Person | None"] = relationship(foreign_keys=[buyer_person_attio_id])
