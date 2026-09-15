"""`feedback_submissions` — the durable record of in-app feedback pushed by
the WusoolScribe desktop app (`POST /desktop/feedback`, `meetings` module).

The row is the source of truth; email (SES, via `notifications`) is a
best-effort notification about it, not the record itself — a submission
that fails to email is not a submission that gets lost.
`email_sent`/`email_sent_at` exist so that failure mode stays visible
(queryable) rather than silent, since the endpoint deliberately doesn't
fail the request over it.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Text, literal_column, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackSubmission(Base):
    __tablename__ = "feedback_submissions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('bug','feature_request','transcription_quality','other')",
            name="feedback_submissions_category_check",
        ),
        Index("idx_feedback_submissions_created_at", literal_column("created_at DESC")),
        Index("idx_feedback_submissions_install_id", "install_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(Text)
    install_id: Mapped[str] = mapped_column(Text, nullable=False)
    app_version: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
