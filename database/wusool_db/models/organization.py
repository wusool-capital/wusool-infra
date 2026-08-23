"""`organizations` — the parent entity. Buyer/seller roles are memberships on
it, never independent records (see `database/sql/002_core_attio_mirror.sql`,
`003_crm_roles.sql`).

Union of two independently-evolved mappings that stood in for `wusool-db`
before Stage 1 of the Alembic migration (see `ALEMBIC_MIGRATION_HANDOVER.md`):
matching-engine's mapped every column it needed for matching (`type`,
`stage_focus`, `domains`, `categories`, `connection_strength`,
`owner_attio_id`, `last_interaction_at`, `raw_attio`, `created_at`,
`updated_at`, plus the cross-module relationships), while ddl-commands'
mapped `estimated_arr`/`funding_raised`/`removed_at` on top of the columns
both shared — these three are actively read/written by `/edit-seller` and
`/edit-buyer` (`ddl_commands/shared/organization_field_spec.py`,
`organization_schemas.py`, `modules/slack/handlers/actions.py`) and are not a
subset of matching-engine's columns, so neither prior mapping alone is a
superset of the other. This is the union of both — not a re-narrowing.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.buyer_role import BuyerRole
    from wusool_db.models.deal import Deal
    from wusool_db.models.person import Person
    from wusool_db.models.seller_role import SellerRole


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        Index("idx_organizations_domains", "domains", postgresql_using="gin"),
        Index("idx_organizations_type", "type", postgresql_using="gin"),
        Index(
            "ix_organizations_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    client_type: Mapped[str | None] = mapped_column(Text)
    sector_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    stage_focus: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    geographic_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    hq_country: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    relationship_status: Mapped[str | None] = mapped_column(Text)
    connection_strength: Mapped[str | None] = mapped_column(Text)
    owner_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.attio_id", name="organizations_owner_attio_id_fkey")
    )
    last_interaction_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # ddl-commands-originated columns (see module docstring) — Attio-mirrored,
    # editable via `/edit-seller`/`/edit-buyer`'s organization-level fields.
    estimated_arr: Mapped[str | None] = mapped_column(Text)
    # Money shape confirmed from database/sync-postgres.ps1: {"amount": ..., "currency": ...}
    # or the column is NULL entirely — never fabricated when absent.
    funding_raised: Mapped[dict | None] = mapped_column(JSONB)
    # Attio-owned (database/sql/002_core_attio_mirror.sql, set/cleared by
    # database/sync-postgres.ps1) — read-only from the apps' perspective,
    # checked before any Attio write so a bot never PATCHes a record Attio no
    # longer has.
    removed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact) — all plain text/number/date, no
    # money-shape wrapping needed for any of these.
    angellist: Mapped[str | None] = mapped_column(Text)
    facebook: Mapped[str | None] = mapped_column(Text)
    instagram: Mapped[str | None] = mapped_column(Text)
    twitter: Mapped[str | None] = mapped_column(Text)
    twitter_follower_count: Mapped[int | None] = mapped_column(Integer)
    foundation_date: Mapped[date | None] = mapped_column()
    ticket_size: Mapped[str | None] = mapped_column(Text)
    lead_source: Mapped[str | None] = mapped_column(Text)
    # Added 2026-08-19: SOURCE's own bands adopted as-is (1-10, 11-50, 51-250,
    # 251-1K, 1K-5K, 5K-10K, 10K-50K, 50K-100K, 100K+) — the earlier requested
    # target bands were dropped in favor of not needing a reconciliation table.
    employee_range: Mapped[str | None] = mapped_column(Text)
    linkedin: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    # Added 2026-08-20 alongside DEV Attio organizations.is_active (Wusool
    # Schema Handover artifact): true for the newest SOURCE record in a
    # duplicate-name group, false for older duplicates, true for a unique
    # name. Mirrors DEV as-is -- not filtered on here, since Postgres already
    # holds one row per organization (no duplicate rows to prefer between).
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_role: Mapped["BuyerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    seller_role: Mapped["SellerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    people: Mapped[list["Person"]] = relationship(back_populates="company")
    deals_as_buyer: Mapped[list["Deal"]] = relationship(
        foreign_keys="Deal.buyer_organization_attio_id", back_populates="buyer_organization"
    )
    deals_as_seller: Mapped[list["Deal"]] = relationship(
        foreign_keys="Deal.seller_organization_attio_id", back_populates="seller_organization"
    )
