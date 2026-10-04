"""`DiscrepancyCheckService` orchestration — an empty note never calls the
extractor; an extracted note is grounded, then feeds the rules; an extraction
failure still lists what's missing and flags the note as unchecked.
"""

import pytest

from app.modules.discrepancies.application.check import DiscrepancyCheckService
from app.modules.discrepancies.domain.criteria import BuyerCriteria, ParsedContext
from app.modules.discrepancies.tests.fakes.context_extractor import FakeContextExtractor

_CRITERIA = BuyerCriteria(
    buyer_role_id="role-1",
    org_name="Shahroukh Capital",
    target_vertical="Pharmaceuticals / Biotech",
    target_region=["GCC"],
    check_size_min=5_000_000.0,
    check_size_max=15_000_000.0,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("context_text", [None, "", "   "])
async def test_empty_note_never_calls_the_extractor(context_text: str | None) -> None:
    extractor = FakeContextExtractor(ParsedContext(vertical="Garage"))
    service = DiscrepancyCheckService(extractor=extractor)

    result = await service.check(_CRITERIA, context_text)

    assert extractor.texts == []
    assert result.context_checked
    assert result.report.conflicts == ()


@pytest.mark.asyncio
async def test_extracted_conflict_is_reported() -> None:
    extractor = FakeContextExtractor(
        ParsedContext(ticket_low=50_000_000.0, ticket_high=50_000_000.0)
    )
    service = DiscrepancyCheckService(extractor=extractor)

    result = await service.check(_CRITERIA, "ticket size $50M")

    assert extractor.texts == ["ticket size $50M"]
    assert result.context_checked
    assert [d.criterion.value for d in result.report.conflicts] == ["ticket_band"]
    assert result.message.startswith("Heads up: Shahroukh Capital's profile says ticket band")


@pytest.mark.asyncio
async def test_amounts_the_note_never_names_are_dropped_before_the_rules() -> None:
    extractor = FakeContextExtractor(
        ParsedContext(ticket_low=50_000_000.0, ticket_high=50_000_000.0)
    )
    service = DiscrepancyCheckService(extractor=extractor)

    result = await service.check(_CRITERIA, "targets with $50M revenue")

    assert result.context_checked
    assert result.report.conflicts == ()


@pytest.mark.asyncio
async def test_extraction_failure_still_lists_missing_and_never_claims_clear() -> None:
    service = DiscrepancyCheckService(extractor=FakeContextExtractor(RuntimeError("bedrock down")))

    result = await service.check(_CRITERIA, "ticket size $50M")

    assert not result.context_checked
    assert result.report.conflicts == ()
    assert [d.criterion.value for d in result.report.missing] == ["ebitda"]
    assert "EBITDA" in result.message
    assert "couldn't be checked for conflicts" in result.message
    assert "no missing or conflicting" not in result.message.lower()
