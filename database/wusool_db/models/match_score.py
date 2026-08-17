"""`match_scores` — the pre-existing deterministic scoring breakdown (see
`004_machine_layer.sql`): one row per scored buyer/seller pair (score/dims/
reasoning/citations). Phase 3 writes one row here per STAGE3_TOP_N
shortlisted candidate only — not for every stage-1 survivor (see
`workflows/crm-sync/docs/PHASE3_MATCH_RESULTS_HANDOVER.md`).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, Text, literal_column, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class MatchScore(Base):
    __tablename__ = "match_scores"
    __table_args__ = (
        Index(
            "idx_match_scores_pair_generated",
            "buyer_attio_id",
            "seller_attio_id",
            literal_column("generated_at DESC"),
        ),
    )

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
