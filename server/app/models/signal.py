"""`signals` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Clean, no ambiguity: not touched again after `004_machine_layer.sql`.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, literal_column, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        # Added NOT VALID in the migration: the draft table never had a closed list.
        CheckConstraint(
            "source IN ('transcript','news','linkedin','jobs')", name="signals_source_check"
        ),
        Index("idx_signals_buyer_ts", "buyer_attio_id", literal_column("ts DESC")),
        # Partial index -- must match the migration exactly or `alembic check`
        # reports drift.
        Index(
            "uq_signals_source_external_id",
            "source",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    buyer_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    rank: Mapped[int | None] = mapped_column(Integer)
    source_cite: Mapped[str | None] = mapped_column(Text)
    # Stable id in the upstream source (post URN, transcript item id) so a
    # re-scrape cannot insert the same signal twice.
    external_id: Mapped[str | None] = mapped_column(Text)
    tool_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("tool_runs.id"))
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("meetings.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_organization: Mapped["Organization"] = relationship(foreign_keys=[buyer_attio_id])
