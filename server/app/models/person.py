"""`person` — renamed from `people` 2026-08-30; see `002_core_attio_mirror.sql`."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (
        Index("idx_person_company", "company_attio_id"),
        Index("idx_person_email", "email", postgresql_using="gin"),
    )

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    company_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    email: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    linkedin: Mapped[str | None] = mapped_column(Text)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    connection_strength: Mapped[str | None] = mapped_column(Text)
    owner_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.attio_id", name="person_owner_attio_id_fkey")
    )
    past_employers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    education: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    enrichment: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_interaction_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # Added 2026-08-19 alongside the DEV Attio attributes of the same names
    # (Wusool Schema Handover artifact).
    job_title: Mapped[str | None] = mapped_column(Text)
    contact_type: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    angellist: Mapped[str | None] = mapped_column(Text)
    facebook: Mapped[str | None] = mapped_column(Text)
    instagram: Mapped[str | None] = mapped_column(Text)
    twitter: Mapped[str | None] = mapped_column(Text)
    twitter_follower_count: Mapped[int | None] = mapped_column(Integer)
    # Added 2026-08-23, mirrors organizations.removed_at: sync-postgres.ps1
    # soft-deletes (instead of hard-deleting) a person no longer present in
    # DEV Attio, since buyer_roles.key_contact_attio_id and
    # deals.buyer_person_attio_id both reference person with ON DELETE NO
    # ACTION -- a hard delete would fail outright (or silently break a
    # still-valid buyer role/deal's contact) if either still points at it.
    removed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped["Organization | None"] = relationship(back_populates="people")
