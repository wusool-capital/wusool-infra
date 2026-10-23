"""`linkedin_scans` — enrichment's run ledger for LinkedIn scans (AZM-148).

One row per attempted scan, succeeded or failed. `activities` links to it
(`ledger_type='linkedin_scan'`) and the scan's `signals` point back at it.
Each module owns its own ledger: this one is written only by `enrichment`,
as `command_runs` is by `ddl_commands`. Postgres-only, never written to Attio.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, literal_column, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LinkedInScan(Base):
    __tablename__ = "linkedin_scans"
    __table_args__ = (
        CheckConstraint("status IN ('succeeded','failed')", name="linkedin_scans_status_check"),
        Index("idx_linkedin_scans_org_started", "org_attio_id", literal_column("started_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    # The scans (and their signals) leave with the organization: they hold personal data.
    org_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    seller_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("seller_roles.id", ondelete="SET NULL")
    )
    buyer_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("buyer_roles.id", ondelete="SET NULL")
    )
    # Slack user id of whoever triggered it; NULL when the system did.
    requested_by: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # The exception type only, never its message: it can quote row values.
    error: Mapped[str | None] = mapped_column(Text)
    posts_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    job_changes_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    contacts_scanned: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    contacts_without_linkedin: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
