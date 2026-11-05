"""`interactions` — one Gmail message or Calendar event occurrence per mailbox (AZM-159).

Written only by the interactions engine from header/event metadata; bodies are
never stored. Postgres-only, never written to Attio.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Text, UniqueConstraint, literal_column, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        CheckConstraint("channel IN ('email','meeting')", name="interactions_channel_check"),
        CheckConstraint(
            "direction IS NULL OR direction IN ('inbound','outbound')",
            name="interactions_direction_check",
        ),
        UniqueConstraint("mailbox", "channel", "source_id", name="uq_interactions_mailbox_source"),
        Index("idx_interactions_dedupe_key", "dedupe_key"),
        Index("idx_interactions_occurred_at", literal_column("occurred_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    mailbox: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    # Gmail message id or Calendar event id; differs per mailbox.
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    # Message-ID header, or iCalUID plus start; same across mailboxes, so counted once.
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # NULL for meetings.
    direction: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
