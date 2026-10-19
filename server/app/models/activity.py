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
meaningful event (actor, `event_type`, subject, `ts`, `outcome`) plus a typed
FK to the domain ledger holding the detail. `ts` is event time, `created_at`
is insert time. See `docs/internal/dev/ACTIVITIES_AUDIT.md`.
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
            "num_nonnulls(tool_run_id, match_result_id, meeting_id, command_run_id, "
            "deal_stage_event_id, signal_id) <= 1",
            name="activities_single_ledger_link",
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
    # Links a timeline row back to the tool invocation that produced it
    # (2026-09-06). Nullable: most activities are human interactions with no
    # run behind them. See app/models/tool_run.py for why runs live in their
    # own table rather than here.
    tool_run_id: Mapped[uuid_.UUID | None] = mapped_column(UUID, ForeignKey("tool_runs.id"))
    # `domain.verb`, e.g. `seller.added`. The closed list lives in
    # `app.modules.activities.domain.vocabulary.EventType`.
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Raw actor id: Slack user, Attio member/token, Scribe install, process name.
    actor_ref: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    # Typed links to the ledger row holding the detail. At most one is set
    # (`activities_single_ledger_link`); the index row never copies ledger data.
    match_result_id: Mapped[uuid_.UUID | None] = mapped_column(
        UUID, ForeignKey("match_results.id", ondelete="SET NULL")
    )
    meeting_id: Mapped[uuid_.UUID | None] = mapped_column(
        UUID, ForeignKey("meetings.id", ondelete="SET NULL")
    )
    command_run_id: Mapped[uuid_.UUID | None] = mapped_column(
        UUID, ForeignKey("command_runs.id", ondelete="SET NULL")
    )
    deal_stage_event_id: Mapped[uuid_.UUID | None] = mapped_column(
        UUID, ForeignKey("deal_stage_events.id", ondelete="SET NULL")
    )
    signal_id: Mapped[uuid_.UUID | None] = mapped_column(
        UUID, ForeignKey("signals.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_attio_id])
