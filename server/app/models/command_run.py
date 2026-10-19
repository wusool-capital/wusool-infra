"""`command_runs` — the ledger for Slack and discovery add/edit seller/buyer commands.

Mirrors `tool_runs` for the Slack side. A command is Attio-first then
Postgres, so it can fail or land halfway (`partial`) before any role row
exists; `activities` cannot record that because it requires a subject. Every
subject reference here is nullable for the same reason.

`activities` rows for successful commands link back here through
`activities.command_run_id`. Postgres-only, never written to Attio.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, literal_column, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CommandRun(Base):
    __tablename__ = "command_runs"
    __table_args__ = (
        CheckConstraint(
            "command IN ('add_seller','add_buyer','edit_seller','edit_buyer')",
            name="command_runs_command_check",
        ),
        CheckConstraint(
            "invoked_via IN ('slack','discovery')",
            name="command_runs_invoked_via_check",
        ),
        CheckConstraint(
            "status IN ('running','succeeded','failed','partial')",
            name="command_runs_status_check",
        ),
        Index("idx_command_runs_started_at", literal_column("started_at DESC")),
        Index("idx_command_runs_organization", "org_attio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    invoked_via: Mapped[str] = mapped_column(Text, nullable=False)
    # Slack user id for Slack commands; NULL for discovery.
    requested_by: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    org_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    seller_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("seller_roles.id"))
    buyer_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("buyer_roles.id"))
    # Attio writes that landed before a failure, e.g. "organization".
    landed: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    # Field names only, never values: values can hold PII.
    changed_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
