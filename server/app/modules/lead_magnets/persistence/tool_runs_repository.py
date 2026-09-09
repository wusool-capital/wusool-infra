"""The write-ahead ledger. Every lead-magnet submission gets a row here
before any AI or Attio call, so nothing that fails afterwards can lose it.

Transaction boundaries belong to the caller, per this repo's repository
convention: `execute`/`flush` only, never `commit`/`rollback`.
"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, ScalarSelect, and_, case, func, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.buyer_role import BuyerRole
from app.models.person import Person
from app.models.seller_role import SellerRole
from app.models.tool_run import ToolRun
from app.modules.lead_magnets.domain.tool_run import (
    Stage,
    SubjectRefs,
    Tool,
    ToolRunRecord,
    ToolRunStatus,
)
from app.modules.organizations import OrganizationRepository
from app.modules.utilities.domain.json_types import JsonObject

# `payload->>'stage'`, as SQL. The sweeper's ceilings key off it.
_STAGE = ToolRun.payload["stage"].astext

# Per-failure-class retry ceilings, applied as one CASE so a row is never
# claimed past its own limit. Retrying a failed Attio write is free and
# idempotent — the AI output is already paid for and stored. Retrying a
# failed AI call is not, so those resume from the deterministic fallback
# instead, and readiness — which has no fallback by decision — is never
# retried at all.
_NO_SUBJECTS = SubjectRefs()

_CEILING = case(
    (and_(_STAGE == "ai", ToolRun.tool == "readiness"), 1),
    (_STAGE == "ai", 2),
    else_=6,
)


def _to_record(row: ToolRun) -> ToolRunRecord:
    payload = row.payload or {}
    return ToolRunRecord(
        id=row.id,
        tool=row.tool,
        status=row.status,
        attempt_count=row.attempt_count,
        payload=payload,
        stage=payload.get("stage"),
    )


class ToolRunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._organizations = OrganizationRepository(session)

    async def start(
        self, *, tool: Tool, payload: JsonObject, idempotency_key: str
    ) -> tuple[UUID, bool]:
        """Step 1 of the write contract. Returns `(run_id, is_new)`.

        `is_new=False` means this exact submission is already in flight or
        done — a double-clicked button or a retried POST — and the caller
        must not run the pipeline again.

        `idempotency_key` is never allowed to be None here even though the
        column is nullable: Postgres permits unlimited NULLs in a UNIQUE
        column, so a NULL key would silently opt every such row out of the
        deduplication this exists to provide.
        """
        stmt = (
            pg_insert(ToolRun)
            .values(
                tool=tool,
                status="running",
                payload=payload,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(ToolRun.id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted is not None:
            return inserted, True

        existing = (
            await self._session.execute(
                select(ToolRun.id).where(ToolRun.idempotency_key == idempotency_key)
            )
        ).scalar_one()
        return existing, False

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
        await self._session.execute(update(ToolRun).where(ToolRun.id == run_id).values(**values))

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
        return [_to_record(row) for row in rows]

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
        return [_to_record(row) for row in rows]

    async def promote_role_fks(self) -> int:
        """Fills in role FKs left NULL because the Attio→Postgres mirror had
        not landed the role row when `finish()` ran. Idempotent.
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
                            model.legacy_entry_id == ToolRun.payload[key].astext,
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
        return None if row is None else _to_record(row)
