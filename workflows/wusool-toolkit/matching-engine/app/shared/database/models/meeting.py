"""`meetings` — read-only from this app's perspective. Owned and written by
Scribe (its own standalone Postgres/Alembic chain) and by the one-time Attio
notes migration; this app only ever SELECTs. DDL lives in
database/sql/005_meetings.sql, one level above this repo.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base

# Native Postgres enums (005_meetings.sql) — create_type=False since this app
# never creates the schema, only reads it; values must match the DDL exactly.
_MeetingSource = ENUM(
    "in_house", "granola", "manual", name="meeting_source", create_type=False
)
_CounterpartyRole = ENUM("buyer", "seller", name="counterparty_role", create_type=False)
_MeetingType = ENUM(
    "enrichment", "alignment", "owner_iv", "buyer_intro", "internal",
    name="meeting_type", create_type=False,
)


class Meeting(Base):
    __tablename__ = "meetings"

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
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    scribe_meeting_id: Mapped[UUID | None] = mapped_column(unique=True)
