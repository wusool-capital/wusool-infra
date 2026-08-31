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
    buyer_person_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("person.attio_id"))
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
    data_room_substatus: Mapped[str | None] = mapped_column(Text)
    comparables: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact). `estimated_deal_value_usd` and `fee`
    # are real DEV Attio type "number" (plain scalar), not "currency" — no
    # money-shape wrapping, unlike `value` above. `assigned_advisor` is a
    # plain multiselect of advisor names, not a workspace-member/User FK.
    # Renamed from `estimated_deal_value_aed` 2026-08-25 (AED -> USD cleanup);
    # see c1a9f4e83d67's follow-up migration.
    nda_status: Mapped[str | None] = mapped_column(Text)
    estimated_deal_value_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    expected_close_date: Mapped[date | None] = mapped_column()
    fee: Mapped[Decimal | None] = mapped_column(Numeric)
    assigned_advisor: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    # Merged in from the retired Mandates list, 2026-08-23 (see
    # migration-decisions.json and the Wusool Schema Handover artifact): the
    # one-mandate-to-many-deals model Mandate was built for was never
    # actually used (neither of the 2 real DEV Mandate entries had a linked
    # Deal), so every Mandate entry became its own Deal record instead.
    # `deal_type` replaces Mandate's `side`. `phase` was deliberately not
    # carried over -- a manually-typed label that only restates
    # universe_constructed/universe_size/shortlist_approved/shortlist_size/
    # tier1_contacted/responses, and can drift out of sync with those
    # numbers. `counterparty_interested` renames Mandate's
    # `sellers_interested`, which only read correctly on a buy-side mandate.
    # `mandate_start_date`/`mandate_expiry_date` are named for disambiguation
    # against `contract_signed_date`/`exclusivity_date`/`expected_close_date`
    # above -- the DEV Attio attributes are still slugged start_date/
    # expiry_date, only the display titles changed. `assigned_advisor` above
    # is reused as-is, not replaced with Mandate's `user-reference[]`-typed
    # version: Attio can't change a field's type in place, and a second
    # parallel "who's the advisor" field would be worse than reusing this
    # one. All 58 pre-existing Deals were backfilled to deal_type=Sell-side:
    # confirmed directly from SOURCE's `deals` attribute list, which has no
    # buyer-referencing field at all (only `associated_company` -> seller),
    # so every Deal ever migrated from SOURCE is sell-side by construction.
    deal_type: Mapped[str | None] = mapped_column(Text)
    universe_constructed: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    universe_size: Mapped[int | None] = mapped_column()
    shortlist_approved: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    shortlist_size: Mapped[int | None] = mapped_column()
    tier1_contacted: Mapped[int | None] = mapped_column()
    responses: Mapped[int | None] = mapped_column()
    counterparty_interested: Mapped[int | None] = mapped_column(Integer)
    mandate_start_date: Mapped[date | None] = mapped_column()
    mandate_expiry_date: Mapped[date | None] = mapped_column()
    retainer_amount: Mapped[dict | None] = mapped_column(JSONB)
    # Idempotency key for the one-time Mandate-to-Deal migration
    # (`Invoke-Deals -MigrateMandates` in
    # workflows/crm-sync/scripts/_internal/objects.ps1) -- not a business
    # field, lets that migration re-run without creating duplicate Deals.
    source_mandate_entry_id: Mapped[str | None] = mapped_column(Text, unique=True)
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
