"""`meetings` — written by Scribe (its own standalone Postgres/Alembic chain)
and by the one-time Attio notes migration; also written by this repo's own
`meetings` module (landing in a later phase), which owns the desktop-push
columns added below. DDL lives in `(historical, removed) database/sql/005_meetings.sql`.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Native Postgres enums (005_meetings.sql) — create_type=False is kept because
# the baseline revision d982478fc6e3 already owns CREATE TYPE for these three
# enums (they must exist before this table does); autogenerate must not try
# to re-emit them here. Values must match the DDL exactly. Do not flip this
# to create_type=True: an `alembic upgrade head` against an empty database
# needs d982478fc6e3's hand-written CREATE TYPE to run first (see
# ALEMBIC_MIGRATION_HANDOVER.md point 4).
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
        CheckConstraint(
            "status IN ('summarizing','completed','failed')", name="ck_meetings_status"
        ),
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
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="completed")
    install_id: Mapped[str | None] = mapped_column(Text)
    local_recording_id: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSONB)
    summary_started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
