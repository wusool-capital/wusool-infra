"""The write contract. Every submission goes through this, in this order.

    1. record the submission      <- before any AI or Attio call
    2. respond to the browser     <- the API layer; nothing after it can
                                     lose the lead
    3. AI work
    4. write to Attio, is_test always set
    5. finish the ledger row

Steps 3-5 live in `complete`, which takes a `ToolRunRecord` rather than a
fresh payload. That is deliberate: a first attempt and a sweeper resume are
then the *same* code path, and the row itself says which steps are already
done. A run that has paid for its AI output never pays twice, and a run
whose Attio write already landed never writes twice.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from uuid import UUID

from app.modules.lead_magnets.application.shared.ports import AttioWriterPort, ToolRunsPort
from app.modules.lead_magnets.domain.shared.dedup import idempotency_key
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs, Tool, ToolRunRecord
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

logger = logging.getLogger(__name__)

# `(tool, payload) -> ai output`. Kept as a callable rather than a Protocol
# so `submit.py` needs to know nothing about prompts or models.
AiRunner = Callable[[str, JsonObject], Awaitable[JsonObject]]

# `(tool, payload) -> ai-shaped output, or None when this tool has no
# fallback`. Readiness returns None by decision: its score, band and
# recommendations come only from the model, and no code sums its answers.
FallbackRunner = Callable[[str, JsonObject], JsonObject | None]


class SubmissionService:
    def __init__(
        self,
        *,
        tool_runs: ToolRunsPort,
        attio: AttioWriterPort,
        run_ai: AiRunner,
        fallback: FallbackRunner,
    ) -> None:
        self._tool_runs = tool_runs
        self._attio = attio
        self._run_ai = run_ai
        self._fallback = fallback

    async def record(
        self,
        *,
        tool: Tool,
        payload: JsonObject,
        email: str | None,
        domain: str | None,
    ) -> tuple[UUID, bool]:
        """Step 1. Returns `(run_id, is_new)`; `is_new=False` means this
        person has already completed this tool — the caller must not run
        the pipeline again, and should tell the visitor rather than quietly
        reprocessing.
        """
        return await self._tool_runs.start(
            tool=tool,
            payload=payload,
            idempotency_key=idempotency_key(tool=tool, email=email, domain=domain),
        )

    async def complete(self, run: ToolRunRecord) -> None:
        """Steps 3-5. Never raises: a failure here is recorded on the row and
        left for the sweeper, because the lead is already safe.
        """
        ai = await self._ensure_ai(run)
        if ai is None:
            return
        subjects = await self._ensure_attio(run, ai)
        if subjects is None:
            return
        await self._tool_runs.finish(run.id, "succeeded", subjects=subjects)

    async def _ensure_ai(self, run: ToolRunRecord) -> JsonObject | None:
        """Returns the AI output, or `None` if this run is finished for good.

        A stored `payload.ai` is reused untouched — that output cost money
        and re-earning it is the one thing a resume must not do.
        """
        stored = run.payload.get("ai")
        if isinstance(stored, dict):
            return stored

        try:
            ai = await self._run_ai(run.tool, run.payload)
        except BedrockInvocationError as exc:
            fallback = self._fallback(run.tool, run.payload)
            if fallback is None:
                # Readiness. The visitor sees an error and there is no
                # report to recover; the write-ahead row is what keeps the
                # lead, which is the whole reason step 1 exists.
                logger.warning("lead_magnet_ai_failed_no_fallback tool=%s", run.tool)
                await self._tool_runs.finish(run.id, "failed", error=str(exc))
                return None
            logger.warning("lead_magnet_ai_failed_using_fallback tool=%s", run.tool)
            ai = fallback

        await self._tool_runs.set_stage(run.id, stage="ai", output=ai)
        return ai

    async def _ensure_attio(self, run: ToolRunRecord, ai: JsonObject) -> SubjectRefs | None:
        """Returns what Attio holds for this run, or `None` if the write
        failed and the sweeper should retry it.

        The stage is recorded *before* `finish`, carrying the returned ids,
        so a crash between the two leaves a row that knows Attio is already
        done. Without that, the resume would write Attio a second time and
        duplicate the record.
        """
        stored = run.payload.get("attio")
        if isinstance(stored, dict):
            return SubjectRefs(**stored)

        try:
            subjects = await self._attio.write(tool=run.tool, payload=run.payload, ai=ai)
        except Exception as exc:  # noqa: BLE001 - the lead is already recorded; retry later
            logger.warning("lead_magnet_attio_write_failed tool=%s error=%s", run.tool, exc)
            await self._tool_runs.finish(run.id, "failed", error=str(exc))
            return None

        await self._tool_runs.set_stage(run.id, stage="attio", output=asdict(subjects))
        return subjects
