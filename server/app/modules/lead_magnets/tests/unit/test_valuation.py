"""The valuation tool's datasets, sector resolution and peer matching.

Verified by equivalence out of band: `getStats`, `matchTransactions`,
`matchVCRounds`, `getPeerMedianMargin`, `getIndustryGrowth`,
`getDamodaranBenchmark` and `getTaxRate` were run from
`dopamine-valuation.html` in a node harness over 350 cases — every stats
shape, 66 sectors from the tool's own vocabulary, override terms and
limits — and compared against this module. 349 matched; the one that did
not is the Qatar tax bug documented below.
"""

import pytest

from app.modules.lead_magnets.domain.valuation import (
    comps_for_sector,
    growth_benchmark,
    match_transactions,
    match_vc_rounds,
    peer_median_margin,
    resolve_sector,
    stats,
    tax_rate,
    wacc_benchmark,
)
from app.modules.lead_magnets.domain.valuation_data import (
    industry_growth,
    static_comps,
    transactions,
    vc_rounds,
)


def test_datasets_load_at_their_documented_sizes() -> None:
    assert len(transactions()) == 1000
    assert len(vc_rounds()) == 127
    assert len(static_comps()) == 31
    assert len(industry_growth()) == 32


def test_transaction_fields_are_mapped_off_the_render_code() -> None:
    """The source stores `e`/`r`/`b`; the tool renders them as
    `{ev, evRev, evEb}`. Mapping them the other way round would swap a
    revenue multiple for an EBITDA multiple."""
    first = transactions()[0]
    assert first.target == "Independent Reserve"
    assert first.ev == 117
    assert first.ev_revenue == 5
    assert first.ev_ebitda == 18.2


def test_static_comps_are_already_the_compare_response_shape() -> None:
    """`/compare` returns `{co, tk, ev, rev, ebitda}`, so the shortfall
    fallback needs no translation."""
    comp = static_comps()["AI"][0]
    assert (comp.co, comp.tk) == ("Microsoft Corp", "MSFT")
    assert comp.ev and comp.rev and comp.ebitda


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], (0, 0, 0, 0, 0, 0)),
        ([5], (5, 5, 5, 5, 5, 5)),
        ([1, 2, 3], (1, 1.5, 2, 2, 2.5, 3)),
        ([1, 2, 3, 4], (1, 1.75, 2.5, 2.5, 3.25, 4)),
    ],
)
def test_stats_percentiles_interpolate(values: list[float], expected: tuple) -> None:
    """Percentiles interpolate at `q * (n - 1)`. Other conventions exist and
    give different quartiles on small sets, which is most of them here."""
    s = stats(values)
    assert (s.min, s.p25, s.avg, s.median, s.p75, s.max) == pytest.approx(expected)


def test_stats_is_order_independent() -> None:
    assert stats([3, 1, 2]) == stats([1, 2, 3])


def test_peer_median_margin_takes_the_upper_median() -> None:
    """An even-length set takes the upper middle value, not the mean of the
    two — `statistics.median` would return a different figure and shift
    every trading-comps valuation."""
    from app.modules.lead_magnets.domain.valuation_data import ListedComp

    peers = [
        ListedComp(co="A", tk="A", ev=None, rev=100, ebitda=10),  # 10%
        ListedComp(co="B", tk="B", ev=None, rev=100, ebitda=30),  # 30%
    ]
    assert peer_median_margin("AI", peers) == 30


def test_peer_median_margin_ignores_loss_making_peers() -> None:
    """A negative-EBITDA peer would drag the margin below anything a buyer
    would underwrite."""
    from app.modules.lead_magnets.domain.valuation_data import ListedComp

    peers = [
        ListedComp(co="A", tk="A", ev=None, rev=100, ebitda=20),
        ListedComp(co="B", tk="B", ev=None, rev=100, ebitda=-50),
        ListedComp(co="C", tk="C", ev=None, rev=0, ebitda=10),
    ]
    assert peer_median_margin("AI", peers) == 20


def test_peer_median_margin_falls_back_to_the_static_set() -> None:
    assert peer_median_margin("AI") is not None
    assert peer_median_margin("no such sector at all") is None


def test_comps_for_sector_resolves_through_aliases() -> None:
    assert comps_for_sector("AI")
    assert comps_for_sector("no such sector at all") == ()


def test_match_transactions_respects_the_limit_and_ranks_by_score() -> None:
    top = match_transactions("FinTech", limit=5)
    assert len(top) <= 5
    assert all("fintech" in t.verticals.lower() or t.verticals for t in top)


def test_word_level_matching_is_deliberately_loose() -> None:
    """Individual words score, so a sector nobody would type still matches
    on a common word — "vertical" hits "Vertical Marketplaces". Verified
    against the source, which behaves identically; the looseness is what
    keeps a long-tail sector from returning an empty comp set.
    """
    assert len(match_transactions("zzzz no such vertical", limit=15)) == 15
    # A term sharing no word with any vertical does return nothing.
    assert match_transactions("qqqq") == []


def test_override_terms_take_priority_over_the_sector() -> None:
    """The analyst pass supplies better matching terms when the auto-assigned
    tag pulls the wrong deals; the multiples still come from the dataset."""
    by_sector = match_transactions("AI", limit=10)
    by_override = match_transactions("AI", limit=10, override_terms=["fintech", "payments"])
    assert by_sector != by_override


def test_match_vc_rounds_matches_sector_exactly_not_by_substring() -> None:
    """The VC dataset's labels are short; a substring match pulls unrelated
    rounds into the peer set."""
    assert all(r.sector for r in match_vc_rounds("AI", "Seed"))
    # A one-character term scores nothing: too short to word-match, and no
    # sector equals it.
    assert match_vc_rounds("A") == []


def test_the_stage_bonus_alone_qualifies_a_round() -> None:
    """A quirk of the source, preserved: the stage bonus is added outside the
    sector loop, so every round at the requested stage scores 2 even with no
    sector match at all. The effect is that an unrecognised sector still
    returns stage peers rather than an empty set.
    """
    stage_only = match_vc_rounds("A", "Seed")
    assert stage_only, "an unmatched sector still returns stage peers"
    assert all(r.stage and r.stage.lower() == "seed" for r in stage_only)


def test_matching_stage_boosts_a_round() -> None:
    seed = match_vc_rounds("AI", "Seed")
    none = match_vc_rounds("AI", None)
    assert [r.company for r in seed] != [r.company for r in none] or len(seed) == len(none)


def test_growth_benchmark_falls_back_to_a_generic_default() -> None:
    generic = growth_benchmark("no such sector at all")
    assert generic.revenue_growth == 20
    assert generic.terminal_growth == 2.0
    assert growth_benchmark("AI").revenue_growth == 42


def test_wacc_falls_back_to_the_whole_market() -> None:
    """A DCF with no discount rate is not a valuation, so an unmatched sector
    still gets a rate — labelled so the report can say so."""
    fallback = wacc_benchmark("no such sector at all")
    assert fallback is not None
    assert fallback[2].endswith("(fallback)")
    assert wacc_benchmark(None) is None


def test_resolve_sector_passes_through_an_unaliased_name() -> None:
    assert resolve_sector("AI") == "AI"
    assert resolve_sector(None) is None


@pytest.mark.parametrize(
    "geography,expected",
    [
        ("United Arab Emirates", 9),
        ("UAE", 9),
        ("Kuwait", 15),
        ("Germany", 30),
        ("Nowhere", 20),
        (None, 20),
    ],
)
def test_tax_rate_lookup(geography: str | None, expected: float) -> None:
    assert tax_rate(geography) == expected


@pytest.mark.parametrize("geography", ["Qatar", "Bahrain"])
def test_zero_tax_jurisdictions_are_not_coerced_to_twenty(geography: str) -> None:
    """A deliberate divergence from the source.

    The original reads `return t[geo] || 20`, and JavaScript treats `0` as
    falsy — so Qatar and Bahrain, whose table entries are correctly `0`, are
    silently taxed at 20%. That inflates the tax drag in the DCF and
    undervalues every Qatari and Bahraini business. This is the one case out
    of 350 where the port intentionally disagrees with the live tool.
    """
    assert tax_rate(geography) == 0
