"""The write contract. Every submission goes through this, in this order.

    1. record the submission      <- before any AI or Attio call
    2. respond to the browser     <- the API layer; nothing after it can
                                     lose the lead
    3. AI work
    4. write to Attio, is_test always set
    5. email the visitor a confirmation
    6. email the internal team a notice, with Attio links
    7. finish the ledger row

Steps 3-7 live in `complete`, which takes a `ToolRunRecord` rather than a
fresh payload. That is deliberate: a first attempt and a sweeper resume are
then the *same* code path, and the row itself says which steps are already
done. A run that has paid for its AI output never pays twice, and a run
whose Attio write already landed never writes twice.

Steps 5 and 6 are tracked as two separate stages, not one `email` stage: a
sweeper resume after step 6 fails must short-circuit step 5 rather than
re-send the visitor's confirmation, which already landed.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from uuid import UUID

from app.modules.lead_magnets.application.shared.email_dispatch import (
    build_confirmation_email,
    build_internal_email,
)
from app.modules.lead_magnets.application.shared.ports import AttioWriterPort, ToolRunsPort
from app.modules.lead_magnets.domain.shared.dedup import idempotency_key
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs, Tool, ToolRunRecord
from app.modules.notifications import EmailSenderPort
from app.modules.utilities.domain.json_types import JsonObject

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
        mailer: EmailSenderPort,
        email_from: str,
        email_to: list[str],
    ) -> None:
        self._tool_runs = tool_runs
        self._attio = attio
        self._run_ai = run_ai
        self._fallback = fallback
        self._mailer = mailer
        self._email_from = email_from
        self._email_to = email_to

    async def record(
        self,
        *,
        tool: Tool,
        payload: JsonObject,
        email: str | None,
        domain: str | None,
    ) -> UUID:
        """Step 1. Every submission gets its own permanent row — no
        lookup, no conflict, nothing to block. The caller always proceeds
        to the rest of the pipeline.
        """
        return await self._tool_runs.start(
            tool=tool,
            payload=payload,
            idempotency_key=idempotency_key(email=email, domain=domain),
        )

    async def complete(self, run: ToolRunRecord) -> None:
        """Steps 3-7. Never raises: a failure here is recorded on the row and
        left for the sweeper, because the lead is already safe.

        No-op on an already-`succeeded` run. Every step below already
        reuses stored output rather than redoing paid work, but `finish()`
        itself is not idempotent — it logs a fresh `activities` row on
        every call. Without this guard, a second `run_completion` on the
        same run (an exact-retry's row is completed twice: once for the
        original request, once for the retry) would double the CRM
        activity log even though nothing else was redone.
        """
        if run.status == "succeeded":
            return
        ai = await self._ensure_ai(run)
        if ai is None:
            return
        subjects = await self._ensure_attio(run, ai)
        if subjects is None:
            return
        if await self._ensure_email_confirmation(run, ai, subjects) is None:
            return
        if await self._ensure_email_internal(run, ai, subjects) is None:
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
        except Exception as exc:  # noqa: BLE001 - matches `_ensure_attio`'s own precedent
            # Not narrowed to `BedrockInvocationError`. A pipeline can also
            # raise its own domain-vocabulary error before ever reaching a
            # model — `buyer_network`'s `target_geography` and
            # `get_started`'s `sell_timeline` are both validated inside the
            # `entry_values` builder called from here, not from
            # `_ensure_attio` where sector mapping lives. Narrower catching
            # let such an error escape `complete()` entirely, breaking this
            # method's own "never raises" contract — found live: a crafted
            # `get_started` submission with an unmapped `sell_timeline`
            # propagated out of `complete()` uncaught, and since
            # `sweep_once` claims several stale rows per pass with no
            # per-row isolation, the same exception on a sweeper resume
            # would abort the *entire pass*, rolling back every other row
            # the pass had already finished. Same fix that already exists
            # one line down in `_ensure_attio`.
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

    async def _ensure_email_confirmation(
        self, run: ToolRunRecord, ai: JsonObject, subjects: SubjectRefs
    ) -> bool | None:
        """Step 5. Returns `True` once sent (or nothing to send), `None` if
        the sweeper should retry.

        Skips, permanently, rather than retries, when there is no visitor
        address or no configured sender — that is a config/data gap the
        sweeper re-attempting on a timer cannot fix, and the lead is already
        safe regardless of whether this email goes out.
        """
        if run.payload.get("email_confirmation"):
            return True

        recipient = run.payload.get("email")
        if not isinstance(recipient, str) or not recipient or not self._email_from:
            await self._tool_runs.set_stage(
                run.id, stage="email_confirmation", output={"sent": False}
            )
            return True

        try:
            content = build_confirmation_email(run.tool, run.payload)
            await self._mailer.send(
                to=[recipient],
                from_addr=self._email_from,
                subject=content.subject,
                body=content.html,
                is_html=True,
            )
        except Exception as exc:  # noqa: BLE001 - the lead + Attio write already landed
            logger.warning("lead_magnet_confirmation_email_failed tool=%s error=%s", run.tool, exc)
            await self._tool_runs.finish(run.id, "failed", subjects=subjects, error=str(exc))
            return None

        await self._tool_runs.set_stage(run.id, stage="email_confirmation", output={"sent": True})
        return True

    async def _ensure_email_internal(
        self, run: ToolRunRecord, ai: JsonObject, subjects: SubjectRefs
    ) -> bool | None:
        """Step 6. Same shape as `_ensure_email_confirmation`, sent to the
        internal team instead of the visitor, with Attio links.
        """
        if run.payload.get("email_internal"):
            return True

        if not self._email_to or not self._email_from:
            await self._tool_runs.set_stage(run.id, stage="email_internal", output={"sent": False})
            return True

        try:
            content = build_internal_email(run.tool, run.payload, ai, subjects)
            await self._mailer.send(
                to=self._email_to,
                from_addr=self._email_from,
                subject=content.subject,
                body=content.html,
                is_html=True,
            )
        except Exception as exc:  # noqa: BLE001 - the lead + Attio write already landed
            logger.warning("lead_magnet_internal_email_failed tool=%s error=%s", run.tool, exc)
            await self._tool_runs.finish(run.id, "failed", subjects=subjects, error=str(exc))
            return None

        await self._tool_runs.set_stage(run.id, stage="email_internal", output={"sent": True})
        return True
