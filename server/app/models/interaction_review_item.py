"""`interaction_review_items` — links the interactions engine left for a person (AZM-159).

A shared domain or shared email matches more than one record, so the engine
links nothing and saves the case here. At most one open item per value.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InteractionReviewItem(Base):
    __tablename__ = "interaction_review_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('shared_domain','shared_email')", name="interaction_review_items_kind_check"
        ),
        CheckConstraint(
            "status IN ('open','resolved','dismissed')",
            name="interaction_review_items_status_check",
        ),
        Index(
            "uq_interaction_review_items_open",
            "kind",
            "value",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # The shared address or domain.
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # Subject of the email that raised it, for context in the review digest.
    subject: Mapped[str | None] = mapped_column(Text)
    record_attio_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
