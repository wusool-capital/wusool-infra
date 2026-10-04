"""Orchestration: one Bedrock call reads the advisor's note into a
`ParsedContext`, then deterministic rules and a template do the rest. An
empty note never touches the model; an extraction failure still reports
what's missing and flags the note as unchecked rather than losing the check.
"""

import logging
from dataclasses import dataclass

from app.modules.discrepancies.application.ports.context_extractor import ContextExtractor
from app.modules.discrepancies.domain.criteria import (
    BuyerCriteria,
    DiscrepancyReport,
    ParsedContext,
)
from app.modules.discrepancies.domain.rules import ground, run_checks, template_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscrepancyCheckResult:
    report: DiscrepancyReport
    message: str
    # False when the note couldn't be read, so conflicts may be unflagged.
    context_checked: bool


class DiscrepancyCheckService:
    def __init__(self, *, extractor: ContextExtractor) -> None:
        self._extractor = extractor

    async def check(
        self, criteria: BuyerCriteria, context_text: str | None
    ) -> DiscrepancyCheckResult:
        context = ParsedContext()
        context_checked = True
        if context_text and context_text.strip():
            try:
                context = ground(await self._extractor.extract(context_text), context_text)
            except Exception:
                logger.exception(
                    "discrepancy_context_extraction_failed buyer_role_id=%s",
                    criteria.buyer_role_id,
                )
                context_checked = False

        report = run_checks(criteria, context)
        return DiscrepancyCheckResult(
            report=report,
            message=template_message(criteria, report, context_checked=context_checked),
            context_checked=context_checked,
        )
