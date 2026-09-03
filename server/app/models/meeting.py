"""`meetings` — read-only from matching-engine's perspective. Owned and
written by Scribe (its own standalone Postgres/Alembic chain) and by the
one-time Attio notes migration. DDL lives in `(historical, removed) database/sql/005_meetings.sql`.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Native Postgres enums (005_meetings.sql) — create_type=False since no app in
# this repo creates this schema, only reads it; values must match the DDL
# exactly. Do not flip this to create_type=True: an `alembic upgrade head`
# against an empty database needs a hand-written revision to CREATE TYPE
# before the revision that reaches `meetings` (see
# ALEMBIC_MIGRATION_HANDOVER.md point 4) — flipping this instead would break
# integration tests that run `metadata.create_all()` against a database that
# already has these types.
_MeetingSource = ENUM("in_house", "granola", "manual", name="meeting_source", create_type=False)
_CounterpartyRole = ENUM("buyer", "seller", name="counterparty_role", create_type=False)
_MeetingType = ENUM(
    "enrichment",
    "alignment",
    "owner_iv",
    "buyer_intro",
    "internal",
    name="meeting_type",
    create_type=False,
)


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_org_id", "org_id"),
        Index("ix_meetings_occurred_at", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    org_name_raw: Mapped[str | None] = mapped_column(Text)
    counterparty_role: Mapped[str | None] = mapped_column(_CounterpartyRole)
    meeting_type: Mapped[str | None] = mapped_column(_MeetingType)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(_MeetingSource, nullable=False, server_default="in_house")
    audio_ref: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    created_by_ref: Mapped[str | None] = mapped_column(Text)
    participants: Mapped[dict | None] = mapped_column(JSONB)
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    scribe_meeting_id: Mapped[UUID | None] = mapped_column(unique=True)
