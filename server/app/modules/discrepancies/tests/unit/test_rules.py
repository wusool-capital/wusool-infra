"""Pure-function coverage for `domain/rules.py` — no service construction,
no Bedrock call. Deterministic rules only.
"""

import pytest

from app.modules.discrepancies.domain.criteria import (
    BuyerCriteria,
    Discrepancy,
    DiscrepancyReport,
    ParsedContext,
)
from app.modules.discrepancies.domain.rules import (
    find_conflicts,
    find_missing,
    run_checks,
    template_message,
)
from app.modules.discrepancies.domain.vocabulary import Criterion

_CRITERIA = BuyerCriteria(
    buyer_role_id="role-1",
    org_name="Shahroukh Capital",
    target_vertical="Pharmaceuticals / Biotech",
    target_region=["GCC"],
    target_country=[],
    check_size_min=5_000_000.0,
    check_size_max=15_000_000.0,
    ebitda_floor=2_000_000.0,
    ebitda_ceiling=None,
)


def test_find_conflicts_vertical_mismatch() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(vertical="Garage"))
    assert any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_no_vertical_conflict_on_match() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(vertical="Pharmaceuticals / Biotech"))
    assert not any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_ticket_outside_band() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(ticket_low=20_000_000.0))
    assert any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ticket_inside_band_is_not_flagged() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(ticket_low=10_000_000.0))
    assert not any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ebitda_below_floor() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(ebitda=500_000.0))
    assert any(c.criterion.value == "ebitda" for c in conflicts)


def test_ticket_conflict_message_never_shows_the_literal_none() -> None:
    """Regression: an unset upper/lower bound used to interpolate as the
    literal string "None" in the Slack-facing message."""
    criteria = BuyerCriteria(
        buyer_role_id="role-6",
        org_name="Half Open Capital",
        target_vertical=None,
        check_size_min=5_000_000.0,
        check_size_max=None,
    )
    conflicts = find_conflicts(criteria, ParsedContext(ticket_low=1_000_000.0))
    ticket = next(c for c in conflicts if c.criterion.value == "ticket_band")
    assert "None" not in ticket.stored
    assert "None" not in ticket.stated


def test_ebitda_conflict_message_never_shows_the_literal_none() -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-7",
        org_name="Half Open Capital",
        target_vertical=None,
        ebitda_floor=2_000_000.0,
        ebitda_ceiling=None,
    )
    conflicts = find_conflicts(criteria, ParsedContext(ebitda=500_000.0))
    ebitda = next(c for c in conflicts if c.criterion.value == "ebitda")
    assert "None" not in ebitda.stored


def test_find_conflicts_geography_stated_gcc_covered_by_stored_gcc() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(region="GCC"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_stored_mena_covers_stated_gcc() -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-2",
        org_name="Other Capital",
        target_vertical=None,
        target_region=["MENA"],
    )
    conflicts = find_conflicts(criteria, ParsedContext(region="GCC"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_unresolvable_stored_region_skips_check() -> None:
    """Africa can't be resolved to a country set — stay silent rather than guess."""
    criteria = BuyerCriteria(
        buyer_role_id="role-3",
        org_name="Other Capital",
        target_vertical=None,
        target_region=["Africa"],
    )
    conflicts = find_conflicts(criteria, ParsedContext(region="GCC"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_global_context_never_conflicts() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(region="Global"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_missing_flags_unset_criteria() -> None:
    criteria = BuyerCriteria(buyer_role_id="role-4", org_name="Empty Capital", target_vertical=None)
    missing = find_missing(criteria)
    flagged = {d.criterion.value for d in missing}
    assert flagged == {"vertical", "geography", "ticket_band", "ebitda"}


def test_find_missing_does_not_flag_a_legitimate_zero_floor() -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-5",
        org_name="Zero Floor Capital",
        target_vertical="Retail / E-Commerce",
        target_region=["Global"],
        check_size_min=1.0,
        check_size_max=5.0,
        ebitda_floor=0.0,
    )
    missing = find_missing(criteria)
    assert not any(d.criterion.value == "ebitda" for d in missing)


def test_run_checks_empty_context_has_no_conflicts() -> None:
    assert run_checks(_CRITERIA, ParsedContext()).conflicts == ()


_CURSOR = BuyerCriteria(buyer_role_id="role-8", org_name="Cursor", target_vertical="Pharma")
_VERTICAL_CONFLICT = Discrepancy(Criterion.VERTICAL, "conflict", stored="Pharma", stated="Garage")
_MISSING = (
    Discrepancy(Criterion.GEOGRAPHY, "missing", stored="(not set)"),
    Discrepancy(Criterion.TICKET_BAND, "missing", stored="(not set)"),
    Discrepancy(Criterion.EBITDA, "missing", stored="(not set)"),
)
_CONFLICT_LINE = "Heads up: Cursor's profile says vertical is Pharma, but you said Garage."
_MISSING_LINE = "Heads up: Cursor's profile is missing geography, ticket band and EBITDA."


@pytest.mark.parametrize(
    ("conflicts", "missing", "context_checked", "expected"),
    [
        ((), (), True, "No missing or conflicting details found for Cursor."),
        ((_VERTICAL_CONFLICT,), (), True, _CONFLICT_LINE),
        ((), _MISSING, True, _MISSING_LINE),
        ((_VERTICAL_CONFLICT,), _MISSING, True, f"{_CONFLICT_LINE}\n{_MISSING_LINE}"),
        ((), _MISSING, False, f"{_MISSING_LINE}\nYour note couldn't be checked for conflicts."),
        (
            (),
            (),
            False,
            "Nothing is missing from Cursor's profile, but your note couldn't be checked "
            "for conflicts.",
        ),
    ],
)
def test_template_message_uses_the_approved_wording(
    conflicts: tuple[Discrepancy, ...],
    missing: tuple[Discrepancy, ...],
    context_checked: bool,
    expected: str,
) -> None:
    report = DiscrepancyReport(buyer_role_id="role-8", conflicts=conflicts, missing=missing)
    message = template_message(_CURSOR, report, context_checked=context_checked)
    assert message == expected
    if not context_checked:
        assert "no missing or conflicting" not in message.lower()


def test_template_message_single_missing_item_has_no_join() -> None:
    report = DiscrepancyReport(buyer_role_id="role-8", missing=_MISSING[2:])
    message = template_message(_CURSOR, report, context_checked=True)
    assert message == "Heads up: Cursor's profile is missing EBITDA."
