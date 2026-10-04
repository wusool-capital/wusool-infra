"""Composition root for Slack handlers. `_criteria_reader_port_holder` is
registered once at process startup by `server/main.py` via
`configure_criteria_reader_port` — this module never imports
`matching_engine`, so it cannot build its own adapter; see this module's
own `__init__.py` docstring.
"""

from functools import lru_cache

from app.modules.discrepancies.application.check import (
    DiscrepancyCheckResult,
    DiscrepancyCheckService,
)
from app.modules.discrepancies.application.ports.criteria_reader import BuyerCriteriaReaderPort
from app.modules.discrepancies.application.ports.phraser import DiscrepancyPhraser
from app.modules.discrepancies.bootstrap import build_bedrock_phraser
from app.modules.discrepancies.config import get_settings
from app.modules.discrepancies.domain.criteria import BuyerCriteria

_criteria_reader_port_holder: BuyerCriteriaReaderPort | None = None


def configure_criteria_reader_port(port: BuyerCriteriaReaderPort) -> None:
    global _criteria_reader_port_holder
    _criteria_reader_port_holder = port


def _criteria_reader_port() -> BuyerCriteriaReaderPort:
    if _criteria_reader_port_holder is None:
        raise RuntimeError(
            "discrepancies buyer-criteria-reader port not configured — call "
            "configure_criteria_reader_port() at startup"
        )
    return _criteria_reader_port_holder


@lru_cache
def _phraser() -> DiscrepancyPhraser:
    return build_bedrock_phraser()


def _check_service() -> DiscrepancyCheckService:
    settings = get_settings()
    return DiscrepancyCheckService(
        phraser=_phraser(),
        model_id=settings.aws_bedrock_model_id_extraction,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


async def search_buyers(name: str) -> list[BuyerCriteria]:
    return await _criteria_reader_port().search(name)


async def check_buyer_by_id(
    buyer_role_id: str, context_text: str | None
) -> DiscrepancyCheckResult | None:
    """Used by `/check-buyer`'s picker submission — resolves the buyer
    through the same Port `search_buyers` uses, then runs the check."""
    criteria = await _criteria_reader_port().get(buyer_role_id)
    if criteria is None:
        return None
    return await _check_service().check(criteria, context_text)


async def check_buyer_discrepancies(
    criteria: BuyerCriteria, context_text: str | None
) -> DiscrepancyCheckResult:
    """Used directly by `/find-match` (`matching_engine.api.dependencies
    .find_buyer_discrepancies`), which already has the buyer's full context and
    maps it to `BuyerCriteria` itself — no need to go through the Port's
    own `get()` a second time."""
    return await _check_service().check(criteria, context_text)
