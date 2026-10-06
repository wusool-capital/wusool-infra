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
    extractor = FakeContextExtractor(ParsedContext(verticals=("Garage",)))
    service = DiscrepancyCheckService(extractor=extractor)

    result = await service.check(_CRITERIA, context_text)

    assert extractor.texts == []
    assert result.context_checked
    assert result.report.conflicts == ()


@pytest.mark.asyncio
async def test_buyer_with_nothing_to_conflict_never_calls_the_extractor() -> None:
    extractor = FakeContextExtractor(ParsedContext(verticals=("Garage",)))
    service = DiscrepancyCheckService(extractor=extractor)
    empty = BuyerCriteria(buyer_role_id="role-2", org_name="Empty Capital", target_vertical=None)

    result = await service.check(empty, "fintech in GCC, ticket $5M")

    assert extractor.texts == []
    assert result.context_checked
    assert len(result.report.missing) == 4


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
    assert result.message.startswith("*Doesn't match your note*\n• Ticket band: profile has")


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


@pytest.mark.asyncio
async def test_country_only_buyer_reads_the_note_and_flags_a_different_country() -> None:
    extractor = FakeContextExtractor(ParsedContext(countries=("Egypt",)))
    service = DiscrepancyCheckService(extractor=extractor)
    buyer = BuyerCriteria(
        buyer_role_id="role-3",
        org_name="Riyadh Partners",
        target_vertical=None,
        target_country=["Saudi Arabia"],
    )

    result = await service.check(buyer, "only Egypt")

    assert extractor.texts == ["only Egypt"]
    assert [d.stated for d in result.report.conflicts] == ["Egypt"]


@pytest.mark.asyncio
async def test_result_carries_the_grounded_context_and_echoes_it() -> None:
    # "$3M" is never labelled, so grounding drops it before the echo.
    extractor = FakeContextExtractor(
        ParsedContext(countries=("United Arab Emirates",), ticket_low=3_000_000.0)
    )
    service = DiscrepancyCheckService(extractor=extractor)

    result = await service.check(_CRITERIA, "UAE, around $3M")

    assert result.context == ParsedContext(countries=("United Arab Emirates",))
    assert result.message.endswith("_Read your note as: United Arab Emirates_")


@pytest.mark.asyncio
async def test_extraction_failure_never_echoes_a_reading() -> None:
    service = DiscrepancyCheckService(extractor=FakeContextExtractor(RuntimeError("down")))

    result = await service.check(_CRITERIA, "pharma, UAE")

    assert not result.context_checked
    assert result.context == ParsedContext()
    assert "Read your note as" not in result.message
