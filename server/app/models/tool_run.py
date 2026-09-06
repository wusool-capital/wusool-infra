"""`tool_runs` — the machine ledger for lead-magnet tool invocations.

Complements `activities` rather than replacing it. `activities` answers "what
happened with this counterparty" and is what a human reads on a CRM timeline;
this table answers "what did this invocation do", including the runs that
failed before any subject record existed.

That last case is the reason this is a separate table. `activities` carries
`activities_subject_present` (`CHECK (subject_attio_id IS NOT NULL OR
subject_uuid IS NOT NULL)`), so a submission that fails before its Attio write
cannot be recorded there at all -- which is precisely the lead-loss scenario
the ledger exists to catch. Every subject reference here is nullable and there
is no equivalent constraint.

Postgres-only, never written to Attio -- same posture as `activities`.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, literal_column, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.buyer_role import BuyerRole
    from app.models.organization import Organization
    from app.models.person import Person
    from app.models.seller_role import SellerRole


class ToolRun(Base):
    __tablename__ = "tool_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','succeeded','failed','abandoned')",
            name="tool_runs_status_check",
        ),
        Index("idx_tool_runs_tool", "tool"),
        Index("idx_tool_runs_status", "status"),
        Index("idx_tool_runs_started_at", literal_column("started_at DESC")),
        Index("idx_tool_runs_organization", "organization_attio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # Dedups a retried submission and a replayed Attio webhook alike. Nullable
    # because a first-attempt run has nothing to deduplicate against yet.
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error: Mapped[str | None] = mapped_column(Text)
    # The submission itself plus everything about the run that is not entity
    # data: run metadata (dataset version, UTM, FX rate, completeness), the
    # per-step intermediary output, and the raw questionnaire answers that
    # deliberately have no column of their own.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # All four nullable, by design -- see the module docstring.
    organization_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id")
    )
    person_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("person.attio_id"))
    seller_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("seller_roles.id"))
    buyer_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("buyer_roles.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization | None"] = relationship(foreign_keys=[organization_attio_id])
    person: Mapped["Person | None"] = relationship(foreign_keys=[person_attio_id])
    seller_role: Mapped["SellerRole | None"] = relationship(foreign_keys=[seller_role_id])
    buyer_role: Mapped["BuyerRole | None"] = relationship(foreign_keys=[buyer_role_id])
