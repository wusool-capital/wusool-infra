"""`activities` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

`subject_attio_id`/`subject_uuid` are a polymorphic reference disambiguated
by `subject_type` (e.g. "organization" vs. some UUID-keyed table) — there is
no single table either column can be a real `ForeignKey` to, so both stay
plain columns, same as the DDL. The DB-level guarantee that at least one of
them is populated is `activities_subject_present`
(`CHECK (subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL)`),
reproduced below as a `CheckConstraint` with its original name so a future
`--autogenerate` sees no drift.

Since AZM-150 this is the thin, append-only business-event index: one row per
meaningful event (actor, `event_type`, subject, `ts`, `outcome`) plus a
polymorphic `ledger_type`/`ledger_id` pointer to the domain ledger holding the
detail. `ts` is event time, `created_at` is insert time. A trigger rejects every
UPDATE, DELETE and TRUNCATE. See `docs/internal/dev/ACTIVITIES_AUDIT.md`.
"""

import uuid as uuid_
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, literal_column, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL",
            name="activities_subject_present",
        ),
        CheckConstraint(
            "actor_type IN ('attio_member','attio_api_token','attio_system','slack_user',"
            "'scribe_install','website_visitor','system','unknown')",
            name="activities_actor_type_check",
        ),
        CheckConstraint("event_type ~ '^[a-z_]+[.][a-z_]+$'", name="activities_event_type_format"),
        # Added NOT VALID in the migration: older rows predate the closed list.
        CheckConstraint(
            "subject_type IN ('Organization','Person','Deal','BuyerRole','SellerRole','Note',"
            "'Meeting')",
            name="activities_subject_type_check",
        ),
        CheckConstraint(
            "ledger_type IS NULL OR ledger_type IN ('tool_run','command_run','match_result',"
            "'meeting','deal_stage_event','signal')",
            name="activities_ledger_type_check",
        ),
        CheckConstraint(
            "(ledger_type IS NULL) = (ledger_id IS NULL)", name="activities_ledger_pair"
        ),
        Index("idx_activities_subject", "subject_type", "subject_attio_id"),
        Index("idx_activities_ts", literal_column("ts DESC")),
        Index("idx_activities_tool_run", "tool_run_id"),
        # Partial indexes -- must match the migration exactly or `alembic check`
        # reports drift.
        Index(
            "idx_activities_subject_uuid",
            "subject_type",
            "subject_uuid",
            postgresql_where=text("subject_uuid IS NOT NULL"),
        ),
        Index("idx_activities_event_type_ts", "event_type", literal_column("ts DESC")),
        Index(
            "idx_activities_ledger",
            "ledger_type",
            "ledger_id",
            postgresql_where=text("ledger_id IS NOT NULL"),
        ),
        Index(
            "uq_activities_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid_.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Polymorphic subject reference — see module docstring. No FK: the target
    # table depends on `subject_type` and isn't fixed at the schema level.
    subject_attio_id: Mapped[str | None] = mapped_column(Text)
    subject_uuid: Mapped[uuid_.UUID | None] = mapped_column(UUID)
    actor_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.attio_id"))
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    channel: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Deprecated: replaced by `ledger_type`/`ledger_id`, backfilled from this column.
    tool_run_id: Mapped[uuid_.UUID | None] = mapped_column(UUID, ForeignKey("tool_runs.id"))
    # `domain.verb`, e.g. `seller.added`. The closed list lives in
    # `app.modules.activities.domain.vocabulary.EventType`.
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Raw actor id: Slack user, Attio member/token, Scribe install, process name.
    actor_ref: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    # Polymorphic link to the ledger row holding the detail; `LedgerType` names the
    # table. No FK: an FK action would be an UPDATE, which the append-only trigger
    # forbids. `validate-postgres.ps1` checks for dangling ids.
    ledger_type: Mapped[str | None] = mapped_column(Text)
    ledger_id: Mapped[uuid_.UUID | None] = mapped_column(UUID)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_attio_id])
