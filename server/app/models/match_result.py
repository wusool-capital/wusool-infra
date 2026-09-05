"""`match_results` (Phase 3, `(historical, removed) database/sql/006_match_results.sql`, applied by
the DB team) — the one new, additive table covering everything
`match_runs`/`matches`/`match_evidence`/`approvals` (described but never
implemented per PRD.md §3.3-3.4) would have: run audit, shortlisted results,
status, and approval. Two row kinds distinguished by `rank`:

- `rank IS NULL` — the run/header row. Exactly one per `run_id` (enforced by
  a partial unique index in the DDL). Only run-level columns are meaningful:
  `requested_by`, `model_version`, `requirement_profile_version`,
  `requirement_profile`, `candidates_considered`, `candidates_filtered`,
  `filters_skipped`, `final_candidate_ids`, `vector_queries` (always NULL in
  Branch 1 — no vector retrieval), `execution_duration_ms`, `errors`,
  `started_at`, `completed_at`.
- `rank IS NOT NULL` — a shortlisted candidate row (1..STAGE3_TOP_N per run).
  Only candidate-level columns are meaningful: `seller_attio_id`,
  `seller_role_id`, `match_score_id` (FK to the linked `match_scores` row),
  `match_score`, `data_confidence`, the narrative fields, `status`,
  `approved_by`, `decision`, `decided_at`, `decision_notes`.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.buyer_role import BuyerRole
    from app.models.match_score import MatchScore
    from app.models.organization import Organization
    from app.models.seller_role import SellerRole


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('GENERATED', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'FAILED')",
            name="match_results_status_check",
        ),
        CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')",
            name="match_results_decision_check",
        ),
        Index("idx_match_results_run_id", "run_id"),
        Index("idx_match_results_buyer_role", "buyer_role_id"),
        Index("idx_match_results_status", "status"),
        # Enforces "exactly one run/header row per run_id" — see
        # `(historical, removed) database/sql/006_match_results.sql`.
        Index(
            "uq_match_results_run_header",
            "run_id",
            unique=True,
            postgresql_where=text("rank IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)

    buyer_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    buyer_role_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("buyer_roles.id", ondelete="CASCADE"), nullable=False
    )

    # NULL => run/header row. NOT NULL => shortlisted candidate row (1..N).
    rank: Mapped[int | None] = mapped_column(Integer)

    # Candidate-row-only columns (NULL on the run row):
    seller_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE")
    )
    seller_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("seller_roles.id", ondelete="CASCADE")
    )
    match_score_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("match_scores.id"))
    match_score: Mapped[Decimal | None] = mapped_column(Numeric)
    data_confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    why_chosen_over_alternatives: Mapped[str | None] = mapped_column(Text)
    recommended_pitch: Mapped[str | None] = mapped_column(Text)
    risks_and_gaps: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="GENERATED")
    approved_by: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)

    # Run-row-only columns (NULL on candidate rows):
    requested_by: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(Text)
    requirement_profile_version: Mapped[int | None] = mapped_column(Integer)
    requirement_profile: Mapped[dict | None] = mapped_column(JSONB)
    candidates_considered: Mapped[int | None] = mapped_column(Integer)
    candidates_filtered: Mapped[int | None] = mapped_column(Integer)
    filters_skipped: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    vector_queries: Mapped[dict | None] = mapped_column(JSONB)
    final_candidate_ids: Mapped[list | None] = mapped_column(JSONB)
    execution_duration_ms: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Unstructured future-proofing column; not read or written by this phase.
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_organization: Mapped["Organization"] = relationship(foreign_keys=[buyer_attio_id])
    buyer_role: Mapped["BuyerRole"] = relationship(foreign_keys=[buyer_role_id])
    seller_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[seller_attio_id]
    )
    seller_role: Mapped["SellerRole | None"] = relationship(foreign_keys=[seller_role_id])
    match_score_row: Mapped["MatchScore | None"] = relationship(foreign_keys=[match_score_id])
