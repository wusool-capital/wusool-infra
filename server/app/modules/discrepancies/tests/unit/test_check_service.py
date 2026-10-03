"""`DiscrepancyCheckService` orchestration — a clear report never calls the
phraser; a flagged one calls it once; a phraser failure falls back to the
plain template rather than losing the check.
"""

import pytest

from app.modules.discrepancies.application.check import DiscrepancyCheckService
from app.modules.discrepancies.domain.criteria import BuyerCriteria
from app.modules.discrepancies.domain.rules import template_message
from app.modules.discrepancies.tests.fakes.phraser import FakePhraser

_CRITERIA = BuyerCriteria(
    buyer_role_id="role-1",
    org_name="Shahroukh Capital",
    target_vertical="Pharmaceuticals / Biotech",
    target_region=["GCC"],
    check_size_min=5_000_000.0,
    check_size_max=15_000_000.0,
    ebitda_floor=2_000_000.0,
)


@pytest.mark.asyncio
async def test_clear_report_never_calls_the_phraser() -> None:
    phraser = FakePhraser({"message": "should never be used"})
    service = DiscrepancyCheckService(
        phraser=phraser, model_id="m", temperature=0.2, max_tokens=256
    )

    result = await service.check(_CRITERIA, "no criteria mentioned")

    assert result.report.is_clear
    assert phraser.prompts == []


@pytest.mark.asyncio
async def test_flagged_report_calls_the_phraser_once() -> None:
    phraser = FakePhraser({"message": "Heads up: the ticket size you gave is outside range."})
    service = DiscrepancyCheckService(
        phraser=phraser, model_id="m", temperature=0.2, max_tokens=256
    )

    result = await service.check(_CRITERIA, "ticket size $50M")

    assert not result.report.is_clear
    assert len(phraser.prompts) == 1
    assert result.message == "Heads up: the ticket size you gave is outside range."


@pytest.mark.asyncio
async def test_phraser_error_falls_back_to_template() -> None:
    phraser = FakePhraser("__raise__")
    service = DiscrepancyCheckService(
        phraser=phraser, model_id="m", temperature=0.2, max_tokens=256
    )

    result = await service.check(_CRITERIA, "ticket size $50M")

    assert result.message == template_message(_CRITERIA, result.report)
