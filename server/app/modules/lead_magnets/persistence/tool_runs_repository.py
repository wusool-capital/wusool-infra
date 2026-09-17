"""The write-ahead ledger. Every lead-magnet submission gets a row here
before any AI or Attio call, so nothing that fails afterwards can lose it.

Transaction boundaries belong to the caller, per this repo's repository
convention: `execute`/`flush` only, never `commit`/`rollback`.
"""

import logging
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    CursorResult,
    ScalarSelect,
    and_,
    case,
    func,
    insert,
    literal,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.buyer_role import BuyerRole
from app.models.person import Person
from app.models.seller_role import SellerRole
from app.models.tool_run import ToolRun
from app.modules.lead_magnets.domain.shared.tool_run import (
    Stage,
    SubjectRefs,
    Tool,
    ToolRunRecord,
    ToolRunStatus,
)
from app.modules.lead_magnets.persistence.mappers import to_tool_run_record
from app.modules.organizations import OrganizationRepository
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)

# `payload.stage` records the last step that **completed**, so its absence
# is what identifies a run that failed at the AI step. Reading it as "where
# it failed" instead is inverted, and got a readiness AI failure — the one
# case that must never be retried — the default ceiling of 6.
_STAGE_DONE = func.coalesce(ToolRun.payload["stage"].astext, "")

# Per-failure-class retry ceilings, applied as one CASE so a row is never
# claimed past its own limit.
#
#   nothing completed  -> the AI call failed. Costs money on every attempt.
#   'ai' completed     -> the Attio write failed. Free and idempotent: the
#                         model output is already stored and paid for.
#   'attio' completed  -> only `finish` failed. Equally free.
#
# Readiness has no deterministic fallback by decision, so a resume there
# would have to re-call Bedrock for a report the visitor has already been
# shown an error for. Ceiling 1 means the original attempt and nothing more.
_NO_SUBJECTS = SubjectRefs()

_CEILING = case(
    (and_(_STAGE_DONE == "", ToolRun.tool == "readiness"), 1),
    (_STAGE_DONE == "", 2),
    else_=6,
)

# Must render as the exact literal expression `uq_tool_runs_tool_submission_id`
# (`app/models/tool_run.py`) uses. Postgres matches an `ON CONFLICT` target
# against an index's own text, and `ToolRun.payload["submission_id"]` would
# render the key as a bound parameter, which can never match a static index
# definition — hence raw `text()` here instead of the JSONB accessor.
_SUBMISSION_ID_EXPR = text("(payload ->> 'submission_id')")
_SUBMISSION_ID_PRESENT = text("(payload ->> 'submission_id') IS NOT NULL")


class ToolRunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._organizations = OrganizationRepository(session)

    async def start(self, *, tool: Tool, payload: JsonObject, idempotency_key: str) -> UUID:
        """Step 1 of the write contract. Every distinct submission gets its
        own permanent row — nothing ever blocks this, and nothing merges
        two different attempts together.

        The one exception: an exact retried POST of the very same request
        (identical tool + `submission_id`) reuses that row rather than
        starting a second one. Without this, a plain network-level retry —
        not a new visit, the same click landing twice — would re-run the
        whole pipeline a second time: a second Attio write, a second
        visitor confirmation email, a second internal-team notice, and
        (for readiness) a second billed Bedrock call.

        Enforced atomically by `uq_tool_runs_tool_submission_id`
        (`app/models/tool_run.py`), a partial unique index on
        `(tool, payload->>'submission_id')` — not by `idempotency_key`,
        which only tags a row with its client (`email|domain`) for
        grouping/lookup and is not unique. A payload with no
        `submission_id` at all is outside that index's predicate, so it
        never conflicts and always inserts fresh.
        """
        stmt = (
            pg_insert(ToolRun)
            .values(
                tool=tool,
                status="running",
                payload=payload,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(
                index_elements=[ToolRun.tool, _SUBMISSION_ID_EXPR],
                index_where=_SUBMISSION_ID_PRESENT,
            )
            .returning(ToolRun.id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted is not None:
            return inserted

        # Conflict: an exact retry already has a row for this
        # (tool, submission_id). Only reachable when `payload` actually
        # carries one — that's what the index's own predicate requires for
        # a conflict to be possible — so this lookup is safe unguarded.
        return (
            await self._session.execute(
                select(ToolRun.id).where(
                    ToolRun.tool == tool,
                    ToolRun.payload["submission_id"].astext == payload.get("submission_id"),
                )
            )
        ).scalar_one()

    async def set_stage(
        self, run_id: UUID, *, stage: Stage, output: JsonObject | None = None
    ) -> None:
        """Records that `stage` completed, merging any output into `payload`.

        Merge, not replace: `payload` also holds the original submission and
        the raw questionnaire answers, which have no column of their own.
        """
        merged: JsonObject = {"stage": stage}
        if output is not None:
            merged[stage] = output
        await self._session.execute(
            update(ToolRun)
            .where(ToolRun.id == run_id)
            .values(payload=ToolRun.payload.op("||")(literal(merged, JSONB)))
        )

    async def finish(
        self,
        run_id: UUID,
        status: ToolRunStatus,
        *,
        subjects: SubjectRefs = _NO_SUBJECTS,
        error: str | None = None,
    ) -> None:
        """Step 5. Seeds the mirror's parent rows first so the subject FKs
        are satisfiable — see this module's README on the ordering trap.
        """
        if subjects.org_attio_id is not None and subjects.org_name is not None:
            # Already `ON CONFLICT DO NOTHING`, with the webhook-race
            # rationale documented on the method itself.
            await self._organizations.create(subjects.org_attio_id, subjects.org_name)

        if subjects.person_attio_id is not None and subjects.person_name is not None:
            await self._session.execute(
                pg_insert(Person)
                .values(attio_id=subjects.person_attio_id, name=subjects.person_name)
                .on_conflict_do_nothing(index_elements=["attio_id"])
            )

        values: dict[str, object] = {
            "status": status,
            "finished_at": func.now(),
            "error": error,
            "organization_attio_id": subjects.org_attio_id,
            "person_attio_id": subjects.person_attio_id,
            "seller_role_id": self._role_id(SellerRole, subjects.seller_role_entry_id),
            "buyer_role_id": self._role_id(BuyerRole, subjects.buyer_role_entry_id),
        }
        result = await self._session.execute(
            update(ToolRun).where(ToolRun.id == run_id).values(**values).returning(ToolRun.payload)
        )
        payload = result.scalar_one_or_none() or {}
        await self._log_activity(run_id, subjects, payload)

    async def _log_activity(self, run_id: UUID, subjects: SubjectRefs, payload: JsonObject) -> None:
        """One `activities` row per completed Attio write, joined by
        `tool_run_id`. `activities` CHECKs that a subject is present, which a
        failed run (no resolved Attio id) never has, so this is a no-op
        until `subjects` actually resolved one.

        Best-effort: the Attio write already succeeded by the time this
        runs, so a failure here must never stop `finish()` from marking the
        run succeeded. The insert runs in its own savepoint — without one, a
        failed `execute()` leaves the whole session in pending-rollback, and
        the caller's own `commit()` would then raise and silently discard
        the `tool_runs` status update alongside it.
        """
        if subjects.org_attio_id is not None:
            subject_type, subject_attio_id = "Organization", subjects.org_attio_id
        elif subjects.person_attio_id is not None:
            subject_type, subject_attio_id = "Person", subjects.person_attio_id
        else:
            return
        try:
            async with self._session.begin_nested():
                await self._session.execute(
                    insert(Activity).values(
                        subject_type=subject_type,
                        subject_attio_id=subject_attio_id,
                        source="lead_magnet",
                        tool_run_id=run_id,
                        payload=payload,
                    )
                )
        except Exception:
            logger.exception("lead_magnet_activity_log_failed run_id=%s", run_id)

    @staticmethod
    def _role_id(
        model: type[SellerRole] | type[BuyerRole], entry_id: str | None
    ) -> ScalarSelect[UUID] | None:
        """Resolves the Postgres role row by its Attio list-entry id.

        A scalar subquery rather than a Python lookup: the row may not exist
        yet (the mirror lands it seconds after the Attio write), and a
        subquery over no rows is simply NULL — which is what the column
        should hold until `promote_role_fks` fills it in.
        """
        if entry_id is None:
            return None
        return select(model.id).where(model.legacy_entry_id == entry_id).scalar_subquery()

    async def claim_stale(self, *, cutoff: datetime) -> list[ToolRunRecord]:
        """Atomically claims unfinished runs for one sweep, incrementing
        `attempt_count` and stamping `payload.last_attempt_at`.

        The conditional `UPDATE ... RETURNING` *is* the lock — two sweepers
        cannot claim the same row — the same trick
        `MeetingsRepository.recover_stalled` uses.

        `COALESCE(last_attempt_at, started_at)` is load-bearing: gating on
        `started_at` alone means the cutoff never advances, so every sweep
        re-fires the same row immediately.
        """
        last_attempt = func.coalesce(
            func.cast(ToolRun.payload["last_attempt_at"].astext, ToolRun.started_at.type),
            ToolRun.started_at,
        )
        stmt = (
            update(ToolRun)
            .where(
                and_(
                    ToolRun.status.in_(("running", "failed")),
                    ToolRun.attempt_count < _CEILING,
                    last_attempt < cutoff,
                )
            )
            .values(
                attempt_count=ToolRun.attempt_count + 1,
                payload=ToolRun.payload.op("||")(
                    func.jsonb_build_object("last_attempt_at", func.now())
                ),
            )
            .returning(ToolRun)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_tool_run_record(row) for row in rows]

    async def abandon_past_ceiling(self, *, cutoff: datetime) -> list[ToolRunRecord]:
        """Unfinished runs that have exhausted their class's ceiling. These
        need a human, so the caller alerts on them.
        """
        stmt = (
            update(ToolRun)
            .where(
                and_(
                    ToolRun.status.in_(("running", "failed")),
                    ToolRun.attempt_count >= _CEILING,
                    ToolRun.started_at < cutoff,
                )
            )
            .values(status="abandoned", finished_at=func.now())
            .returning(ToolRun)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_tool_run_record(row) for row in rows]

    async def promote_role_fks(self) -> int:
        """Fills in role FKs left NULL because the Attio→Postgres mirror had
        not landed the role row when `finish()` ran. Idempotent.

        `set_stage(stage="attio", output=asdict(subjects))` merges
        `SubjectRefs` under `payload["attio"]`, not at the top level — the
        role entry ids live at `payload["attio"][key]`, matched here.
        """
        promoted = 0
        for column, model, key in (
            ("seller_role_id", SellerRole, "seller_role_entry_id"),
            ("buyer_role_id", BuyerRole, "buyer_role_entry_id"),
        ):
            # Naming the role table in the WHERE is what makes this render
            # as `UPDATE tool_runs ... FROM <role table>`.
            result = cast(
                CursorResult[Any],
                await self._session.execute(
                    update(ToolRun)
                    .where(
                        and_(
                            getattr(ToolRun, column).is_(None),
                            model.legacy_entry_id == ToolRun.payload["attio"][key].astext,
                        )
                    )
                    .values(**{column: model.id})
                ),
            )
            promoted += result.rowcount or 0
        return promoted

    async def get(self, run_id: UUID) -> ToolRunRecord | None:
        row = (
            await self._session.execute(select(ToolRun).where(ToolRun.id == run_id))
        ).scalar_one_or_none()
        return None if row is None else to_tool_run_record(row)
