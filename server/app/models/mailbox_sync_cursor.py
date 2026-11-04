"""`mailbox_sync_cursors` — per-mailbox Gmail/Calendar sync position (AZM-159).

Polls read only changes since `cursor`; the backfill resumes from
`backfill_page_token`. `last_synced_at` drives the stale-mailbox alert.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MailboxSyncCursor(Base):
    __tablename__ = "mailbox_sync_cursors"
    __table_args__ = (
        CheckConstraint("source IN ('gmail','calendar')", name="mailbox_sync_cursors_source_check"),
    )

    mailbox: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    # Gmail history id or Calendar sync token.
    cursor: Mapped[str | None] = mapped_column(Text)
    backfill_page_token: Mapped[str | None] = mapped_column(Text)
    backfill_completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
