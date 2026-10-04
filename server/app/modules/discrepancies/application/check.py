"""Orchestration: run the deterministic rules, then make the one Bedrock
phrasing call only when something was flagged — a clear report never
touches the model. A phrasing failure falls back to the plain template
rather than losing the check.
"""

import json
import logging
from dataclasses import dataclass

from app.modules.discrepancies.application.ports.phraser import DiscrepancyPhraser
from app.modules.discrepancies.domain.criteria import BuyerCriteria, DiscrepancyReport
from app.modules.discrepancies.domain.rules import run_checks, template_message
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscrepancyCheckResult:
    report: DiscrepancyReport
    message: str


def _build_prompt(criteria: BuyerCriteria, report: DiscrepancyReport) -> str:
    lines = [f"Buyer: {criteria.org_name}"]
    lines.extend(
        f"- {d.criterion.value} conflict: on file '{d.stored}', advisor said '{d.stated}'"
        for d in report.conflicts
    )
    lines.extend(
        f"- {d.criterion.value} is missing from the buyer's profile" for d in report.missing
    )
    return (
        "Write one short, friendly Slack message (2-4 sentences) for an M&A advisor, "
        "summarizing the discrepancies below before they run a match. State facts only, "
        "never invent a number or criterion not listed here. No sign-off and no offer "
        "of further help (e.g. 'Let me know if...').\n\n"
        + "\n".join(lines)
        + '\n\nReturn JSON: {"message": "<the sentence(s)>"}'
    )


def _repair_prompt(raw: JsonObject, error: str) -> str:
    return (
        "Your previous response did not match the required schema.\n"
        f"Error: {error}\n"
        f"Previous response: {json.dumps(raw)}\n"
        "Return corrected, schema-valid JSON only."
    )


class DiscrepancyCheckService:
    def __init__(
        self,
        *,
        phraser: DiscrepancyPhraser | None,
        model_id: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._phraser = phraser
        self._model_id = model_id
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def check(
        self, criteria: BuyerCriteria, context_text: str | None
    ) -> DiscrepancyCheckResult:
        report = run_checks(criteria, context_text)
        message = template_message(criteria, report)

        if not report.is_clear and self._phraser is not None:
            try:
                raw = await self._phraser.phrase_report(
                    model_id=self._model_id,
                    prompt=_build_prompt(criteria, report),
                    repair_prompt_builder=_repair_prompt,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                message = str(raw["message"])
            except Exception:
                logger.exception(
                    "discrepancy_phrasing_failed buyer_role_id=%s", criteria.buyer_role_id
                )

        return DiscrepancyCheckResult(report=report, message=message)
