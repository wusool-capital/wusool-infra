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
    can_conflict,
    find_conflicts,
    find_missing,
    ground,
    run_checks,
    template_message,
)
from app.modules.discrepancies.domain.vocabulary import (
    _DISJOINT_REGIONS,
    REGION_OPTIONS,
    Criterion,
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


def test_find_conflicts_vertical_mismatch() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(verticals=("Garage",)))
    assert any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_no_vertical_conflict_on_match() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(verticals=("Pharmaceuticals / Biotech",)))
    assert not any(c.criterion.value == "vertical" for c in conflicts)


def test_find_conflicts_no_vertical_conflict_when_stored_is_any_candidate() -> None:
    """Options overlap ("biotech" fits two), so any candidate match is no conflict."""
    context = ParsedContext(verticals=("Biotech / Longevity", "Pharmaceuticals / Biotech"))
    assert find_conflicts(_CRITERIA, context) == ()


@pytest.mark.parametrize(
    ("stored", "candidates"),
    [
        ("Diversified / Generalist", ("Pharmaceuticals / Biotech",)),
        ("Pharmaceuticals / Biotech", ("Diversified / Generalist",)),
    ],
)
def test_generalist_vertical_never_conflicts(stored: str, candidates: tuple[str, ...]) -> None:
    criteria = BuyerCriteria(buyer_role_id="role-9", org_name="Gen Capital", target_vertical=stored)
    assert find_conflicts(criteria, ParsedContext(verticals=candidates)) == ()


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (BuyerCriteria(buyer_role_id="r", org_name="Empty", target_vertical=None), False),
        (
            BuyerCriteria(
                buyer_role_id="r",
                org_name="Open",
                target_vertical="Diversified / Generalist",
                target_region=["Global"],
            ),
            False,
        ),
        (BuyerCriteria(buyer_role_id="r", org_name="V", target_vertical="Garage"), True),
        (
            BuyerCriteria(
                buyer_role_id="r", org_name="R", target_vertical=None, target_region=["GCC"]
            ),
            True,
        ),
        (
            BuyerCriteria(buyer_role_id="r", org_name="E", target_vertical=None, ebitda_floor=0.0),
            True,
        ),
    ],
)
def test_can_conflict_only_when_a_stored_criterion_could_conflict(
    criteria: BuyerCriteria, expected: bool
) -> None:
    assert can_conflict(criteria) is expected


def test_vertical_conflict_names_the_most_likely_candidate() -> None:
    context = ParsedContext(verticals=("Clinic", "Dental / Specialist Clinics"))
    conflicts = find_conflicts(_CRITERIA, context)
    assert conflicts[0].stated == "Clinic"


def test_find_conflicts_ticket_outside_band() -> None:
    conflicts = find_conflicts(
        _CRITERIA, ParsedContext(ticket_low=20_000_000.0, ticket_high=20_000_000.0)
    )
    assert any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ticket_inside_band_is_not_flagged() -> None:
    conflicts = find_conflicts(
        _CRITERIA, ParsedContext(ticket_low=10_000_000.0, ticket_high=10_000_000.0)
    )
    assert not any(c.criterion.value == "ticket_band" for c in conflicts)


def test_find_conflicts_ebitda_below_floor() -> None:
    conflicts = find_conflicts(
        _CRITERIA, ParsedContext(ebitda_low=500_000.0, ebitda_high=500_000.0)
    )
    assert any(c.criterion.value == "ebitda" for c in conflicts)


@pytest.mark.parametrize(
    ("low", "high", "conflict"),
    [
        (2_000_000.0, None, False),  # "at least $2M" overlaps $5-15M
        (None, 10_000_000.0, False),  # "up to $10M" overlaps $5-15M
        (20_000_000.0, None, True),  # "at least $20M" is entirely above
        (None, 3_000_000.0, True),  # "up to $3M" is entirely below
        (1_000_000.0, 6_000_000.0, False),  # a range overlapping the band
    ],
)
def test_ticket_conflict_only_when_stated_range_cannot_overlap(
    low: float | None, high: float | None, conflict: bool
) -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(ticket_low=low, ticket_high=high))
    assert any(c.criterion.value == "ticket_band" for c in conflicts) is conflict


def test_ebitda_range_overlapping_the_floor_is_not_a_conflict() -> None:
    context = ParsedContext(ebitda_low=1_000_000.0, ebitda_high=3_000_000.0)
    assert find_conflicts(_CRITERIA, context) == ()


def test_open_bound_reads_naturally_in_the_conflict() -> None:
    conflicts = find_conflicts(_CRITERIA, ParsedContext(ticket_low=20_000_000.0))
    assert conflicts[0].stored == "USD 5,000,000 - USD 15,000,000"
    assert conflicts[0].stated == "at least USD 20,000,000"


_ALL_AMOUNTS = ParsedContext(
    verticals=("Garage",), ticket_low=1.0, ticket_high=2.0, ebitda_low=3.0, ebitda_high=4.0
)


@pytest.mark.parametrize(
    ("note", "keeps_ticket", "keeps_ebitda"),
    [
        ("ticket size $1-2M, EBITDA $3-4M", True, True),
        ("check size $1-2M", True, False),
        ("we invest $1-2M", True, False),
        ("EBITDA of $3-4M", False, True),
        ("$1-2M", False, False),
        ("a deal for $1-2M", False, False),
        ("Investments of $1-2M", True, False),
        ("investor writing $1-2M", True, False),
        ("cheque size $1-2M", True, False),
        ("please double-check fit; $1-2M revenue", False, False),
    ],
)
def test_ground_drops_amounts_the_note_never_names(
    note: str, keeps_ticket: bool, keeps_ebitda: bool
) -> None:
    grounded = ground(_ALL_AMOUNTS, note)
    assert grounded.verticals == ("Garage",)
    assert (grounded.ticket_low is not None) is keeps_ticket
    assert (grounded.ticket_high is not None) is keeps_ticket
    assert (grounded.ebitda_low is not None) is keeps_ebitda
    assert (grounded.ebitda_high is not None) is keeps_ebitda


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
    conflicts = find_conflicts(
        criteria, ParsedContext(ticket_low=1_000_000.0, ticket_high=1_000_000.0)
    )
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
    conflicts = find_conflicts(criteria, ParsedContext(ebitda_low=500_000.0, ebitda_high=500_000.0))
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


@pytest.mark.parametrize(
    ("stored", "stated", "conflict"),
    [
        (["Africa"], "GCC", True),
        (["Latin America"], "Europe", True),
        (["Europe", "Africa"], "GCC", True),
        (["Europe", "GCC"], "GCC", False),
        # Overlapping or fuzzy borders never conflict.
        (["Africa"], "MENA", False),
        (["Europe"], "MENATP", False),
        (["Asia"], "GCC", False),
        (["Asia"], "Southeast Asia", False),
        (["Global"], "Latin America", False),
        (["North America"], "GCC", False),  # legacy value outside the options
    ],
)
def test_find_conflicts_geography_only_for_disjoint_regions(
    stored: list[str], stated: str, conflict: bool
) -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-3", org_name="Other Capital", target_vertical=None, target_region=stored
    )
    conflicts = find_conflicts(criteria, ParsedContext(region=stated))
    assert any(c.criterion.value == "geography" for c in conflicts) is conflict


def test_disjoint_region_table_only_names_real_options() -> None:
    names = {name for pair in _DISJOINT_REGIONS for name in pair}
    assert names <= set(REGION_OPTIONS)


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


def _geo_buyer(regions: list[str], countries: list[str]) -> BuyerCriteria:
    return BuyerCriteria(
        buyer_role_id="role-geo",
        org_name="Geo Capital",
        target_vertical=None,
        target_region=regions,
        target_country=countries,
    )


@pytest.mark.parametrize(
    ("regions", "countries", "stated", "conflicts"),
    [
        # Country-only buyer: a different country conflicts, the same one (any spelling) doesn't.
        ([], ["Saudi Arabia"], ParsedContext(countries=("United Arab Emirates",)), True),
        ([], ["Turkey"], ParsedContext(countries=("Türkiye",)), False),
        # A stored region covers the countries it resolves to.
        (["GCC"], [], ParsedContext(countries=("Egypt",)), True),
        (["GCC"], [], ParsedContext(countries=("United Arab Emirates",)), False),
        (["MENATP"], [], ParsedContext(countries=("Turkey",)), False),
        (["MENA"], [], ParsedContext(countries=("Palestinian Authority",)), False),
        ([], ["Palestinian Authority"], ParsedContext(region="MENA"), False),
        # Region and country are a union: either one covering the place is enough.
        (["GCC"], ["Egypt"], ParsedContext(countries=("Egypt",)), False),
        (
            ["Europe"],
            ["United Arab Emirates"],
            ParsedContext(countries=("United Arab Emirates",)),
            False,
        ),
        # An unresolvable stored region is ruled out only via a disjoint home region.
        (["Europe"], [], ParsedContext(countries=("United Arab Emirates",)), True),
        (["Europe"], [], ParsedContext(countries=("Turkey",)), False),
        (["Global"], [], ParsedContext(countries=("Japan",)), False),
        # A stated region against a country-only buyer.
        ([], ["Germany"], ParsedContext(region="GCC"), True),
        ([], ["Saudi Arabia"], ParsedContext(region="GCC"), False),
        ([], ["Germany"], ParsedContext(region="Europe"), False),
        # Several stated places conflict only when every one falls outside.
        ([], ["Saudi Arabia"], ParsedContext(countries=("Saudi Arabia", "Egypt")), False),
        # No stored geography never conflicts — that's a missing field instead.
        ([], [], ParsedContext(countries=("Egypt",)), False),
    ],
)
def test_geography_conflict_uses_region_and_country_together(
    regions: list[str], countries: list[str], stated: ParsedContext, conflicts: bool
) -> None:
    found = find_conflicts(_geo_buyer(regions, countries), stated)
    assert any(c.criterion is Criterion.GEOGRAPHY for c in found) is conflicts


def test_geography_conflict_lists_both_stored_fields() -> None:
    (conflict,) = find_conflicts(
        _geo_buyer(["GCC"], ["Egypt"]), ParsedContext(countries=("Germany",))
    )
    assert conflict.stored == "GCC, Egypt"
    assert conflict.stated == "Germany"


def test_country_only_buyer_can_conflict() -> None:
    assert can_conflict(_geo_buyer([], ["Saudi Arabia"]))


@pytest.mark.parametrize(
    ("regions", "countries", "missing"),
    [([], [], True), (["GCC"], [], False), ([], ["Egypt"], False), (["GCC"], ["Egypt"], False)],
)
def test_geography_missing_only_when_region_and_country_both_empty(
    regions: list[str], countries: list[str], missing: bool
) -> None:
    flagged = {d.criterion for d in find_missing(_geo_buyer(regions, countries))}
    assert (Criterion.GEOGRAPHY in flagged) is missing


def test_ebitda_ceiling_alone_is_not_missing() -> None:
    criteria = BuyerCriteria(
        buyer_role_id="role-9", org_name="Ceiling Capital", target_vertical=None, ebitda_ceiling=5.0
    )
    assert Criterion.EBITDA not in {d.criterion for d in find_missing(criteria)}


def test_template_message_echoes_what_the_note_was_read_as() -> None:
    context = ParsedContext(
        verticals=("Pharmaceuticals / Biotech",),
        countries=("United Arab Emirates",),
        ticket_low=5_000_000.0,
        ticket_high=15_000_000.0,
    )
    report = DiscrepancyReport(buyer_role_id="role-8")
    message = template_message(_CURSOR, report, context_checked=True, context=context)
    assert message.endswith(
        "_Read your note as: Pharmaceuticals / Biotech · United Arab Emirates · "
        "ticket USD 5,000,000 - USD 15,000,000_"
    )


@pytest.mark.parametrize(("context_checked", "context"), [(True, ParsedContext()), (False, None)])
def test_template_message_skips_the_echo_when_nothing_was_read(
    context_checked: bool, context: ParsedContext | None
) -> None:
    report = DiscrepancyReport(buyer_role_id="role-8")
    message = template_message(_CURSOR, report, context_checked=context_checked, context=context)
    assert "Read your note as" not in message
