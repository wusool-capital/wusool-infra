"""`match_scores` — the only match-related table that exists; see `004_machine_layer.sql`.

There is no `match_runs`/`matches`/`match_evidence` table (PRD.md §3.3-3.4
describes them, never implemented — see the schema-gap note in the Phase 2
plan). Run-level audit fields (candidates_considered, filters_skipped,
execution_duration_ms, vector_queries, etc.) have no column anywhere in the
real schema and are not persisted here — nothing is stuffed into `dims` to
compensate, since that would conflate scoring output with run metadata.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base

if TYPE_CHECKING:
    from app.shared.database.models.organization import Organization


class MatchScore(Base):
    __tablename__ = "match_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    buyer_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    seller_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    dims: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    reasoning: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_organization: Mapped["Organization"] = relationship(foreign_keys=[buyer_attio_id])
    seller_organization: Mapped["Organization"] = relationship(foreign_keys=[seller_attio_id])
