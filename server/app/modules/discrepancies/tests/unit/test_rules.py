"""Pure-function coverage for `domain/rules.py` — no service construction,
no Bedrock call. Deterministic rules only.
"""

import pytest

from app.modules.discrepancies.domain.criteria import BuyerCriteria
from app.modules.discrepancies.domain.rules import (
    find_conflicts,
    find_missing,
    parse_context,
    run_checks,
)

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


def test_parse_context_finds_vertical_and_region() -> None:
    parsed = parse_context("Looking for Pharmaceuticals / Biotech targets in GCC")
    assert parsed.vertical == "Pharmaceuticals / Biotech"
    assert parsed.region == "GCC"


def test_parse_context_prefers_longer_region_phrase() -> None:
    parsed = parse_context("Only interested in Southeast Asia")
    assert parsed.region == "Southeast Asia"


def test_parse_context_word_boundary_avoids_european_false_positive() -> None:
    assert parse_context("A European buyer").region is None


def test_parse_context_ebitda_amount_by_keyword_proximity() -> None:
    assert parse_context("EBITDA floor of $2M").ebitda == 2_000_000.0


def test_parse_context_ticket_amount_by_keyword_proximity() -> None:
    parsed = parse_context("ticket size $5-15M")
    assert parsed.ticket_low == 5_000_000.0
    assert parsed.ticket_high == 15_000_000.0


@pytest.mark.parametrize(
    "text",
    [
        "ticket size $5M-15M",
        "ticket size $5M to $15M",
        "ticket size $5M-15",
    ],
)
def test_parse_context_ticket_range_keeps_the_upper_bound_when_both_sides_have_a_suffix(
    text: str,
) -> None:
    """Regression: each bound used to only read the range's trailing
    suffix, so "$5M-15M" silently collapsed to (5M, 5M) — a real conflict
    against a buyer's upper ticket bound would never have been flagged.
    """
    parsed = parse_context(text)
    assert parsed.ticket_low == 5_000_000.0
    assert parsed.ticket_high == 15_000_000.0


def test_parse_context_ignores_amount_with_no_nearby_keyword() -> None:
    """ "$20M revenue" must never be read as a ticket-size conflict."""
    parsed = parse_context("targets with $20M revenue")
    assert parsed.ticket_low is None
    assert parsed.ebitda is None


def test_parse_context_picks_the_closer_keyword_when_both_are_present() -> None:
    """Regression: a fixed EBITDA-first priority used to win even when the
    ticket keyword actually sat right next to the amount.
    """
    parsed = parse_context("Not ebitda-focused, but ticket size is $5M.")
    assert parsed.ticket_low == 5_000_000.0
    assert parsed.ebitda is None


def test_parse_context_single_letter_suffix_must_attach_without_a_space() -> None:
    """Regression: "5 M&A" used to read as a stated $5M ticket size — a
    single-letter suffix (K/M/B) may only attach directly to the number."""
    parsed = parse_context("we do 5 M&A deals a year, ticket size range applies")
    assert parsed.ticket_low is None
    assert parsed.ticket_high is None


def test_parse_context_normalizes_million_word_and_usd_prefix() -> None:
    assert parse_context("EBITDA of USD 5 million").ebitda == 5_000_000.0


def test_find_conflicts_vertical_mismatch() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("Looking at Garage targets"))
    assert any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_no_vertical_conflict_on_match() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("Pharmaceuticals / Biotech only"))
    assert not any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_ticket_outside_band() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("ticket size $20M"))
    assert any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ticket_inside_band_is_not_flagged() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("ticket size $10M"))
    assert not any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ebitda_below_floor() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("EBITDA of $500K"))
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
    conflicts = find_conflicts(criteria, parse_context("ticket size $1M"))
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
    conflicts = find_conflicts(criteria, parse_context("EBITDA of $500K"))
    ebitda = next(c for c in conflicts if c.criterion.value == "ebitda")
    assert "None" not in ebitda.stored


def test_find_conflicts_geography_stated_gcc_covered_by_stored_gcc() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("GCC only"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_stored_mena_covers_stated_gcc() -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-2",
        org_name="Other Capital",
        target_vertical=None,
        target_region=["MENA"],
    )
    conflicts = find_conflicts(criteria, parse_context("GCC targets only"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_unresolvable_stored_region_skips_check() -> None:
    """Africa can't be resolved to a country set — stay silent rather than guess."""
    criteria = BuyerCriteria(
        buyer_role_id="role-3",
        org_name="Other Capital",
        target_vertical=None,
        target_region=["Africa"],
    )
    conflicts = find_conflicts(criteria, parse_context("GCC targets only"))
    assert not any(c.criterion.value == "geography" for c in conflicts)


def test_find_conflicts_geography_global_context_never_conflicts() -> None:
    conflicts = find_conflicts(_CRITERIA, parse_context("Global mandate"))
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


@pytest.mark.parametrize("context_text", [None, "", "no criteria mentioned here"])
def test_run_checks_clear_report_has_no_conflicts(context_text: str | None) -> None:
    report = run_checks(_CRITERIA, context_text)
    assert report.conflicts == ()
