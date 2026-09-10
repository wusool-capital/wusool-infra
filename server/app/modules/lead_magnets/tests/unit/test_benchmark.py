"""The benchmark scoring engine and its peer dataset.

The port was verified exhaustively out of band: the original JS `rank`,
`bandFor`, `adjust` and `quart` were run in node over 6,860 cases — every
sector, every metric, every revenue band, and for each the lower tail, both
exact outer anchors, an interior midpoint, the median and two upper-tail
values — and compared against this module. Zero mismatches.

What is kept here is the subset that would catch a regression: the boundary
and tail branches, the inversion, the clamps, and dataset invariants. The
hand-picked values below are the ones where an off-by-one in the port would
be silent rather than obvious.
"""

import pytest

from app.modules.lead_magnets.domain.benchmark.benchmark import (
    ANCHOR_PERCENTILES,
    PERCENTILE_COLUMNS,
    adjusted_anchors,
    band_for,
    percentile_rank,
    quartile,
    score_metrics,
)
from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import (
    BANDS,
    SECTORS,
    SME_METRICS,
    STAGES,
    TECH_METRICS,
)

_ANCHORS = (0.0, 5.0, 12.0, 21.0, 32.0)


def test_exact_anchors_return_their_own_percentiles() -> None:
    for anchor, expected in zip(_ANCHORS, ANCHOR_PERCENTILES, strict=True):
        assert percentile_rank(anchor, _ANCHORS) == pytest.approx(float(expected))


def test_interior_value_interpolates_linearly() -> None:
    # Halfway between p25 (5.0) and p50 (12.0) is halfway between 25 and 50.
    assert percentile_rank(8.5, _ANCHORS) == pytest.approx(37.5)


def test_lower_tail_extrapolates_at_fifteen_points_per_step() -> None:
    """Below p10 the slope is 15 percentile points per anchor step, so a
    business under the p10 still gets a graded read rather than the floor.

    Half a step below p10 is 10 - 7.5 = 2.5. A full step would be -5 and hit
    the clamp, which is what `test_lower_tail_clamps_at_one` covers.
    """
    step = _ANCHORS[1] - _ANCHORS[0]
    assert percentile_rank(_ANCHORS[0] - step / 2, _ANCHORS) == pytest.approx(2.5)


def test_lower_tail_clamps_at_one() -> None:
    assert percentile_rank(-10_000, _ANCHORS) == 1.0


def test_upper_tail_clamps_at_ninetynine() -> None:
    assert percentile_rank(10_000, _ANCHORS) == 99.0
    # ...and one step above p90 is 105, clamped to 99.
    assert percentile_rank(_ANCHORS[4] + (_ANCHORS[4] - _ANCHORS[3]), _ANCHORS) == 99.0


def test_flat_anchors_do_not_divide_by_zero() -> None:
    """A sector with a zero-width step must fall back to 1, not raise."""
    assert percentile_rank(5.0, (5.0, 5.0, 5.0, 5.0, 5.0)) is not None
    assert percentile_rank(4.0, (5.0, 5.0, 5.0, 5.0, 5.0)) == 1.0


def test_missing_value_or_anchors_is_none_not_zero() -> None:
    """A metric the visitor left blank must be absent from the score, never
    ranked as a zero."""
    assert percentile_rank(None, _ANCHORS) is None
    assert percentile_rank(5.0, ()) is None


@pytest.mark.parametrize(
    "revenue,expected",
    [
        (0, "micro"),
        (544_999, "micro"),
        (545_000, "small"),
        (2_724_999, "small"),
        (2_725_000, "mid"),
        (8_169_999, "mid"),
        (8_170_000, "upper"),
        (100_000_000, "upper"),
    ],
)
def test_band_boundaries_are_exclusive_upper(revenue: float, expected: str) -> None:
    assert band_for(revenue, BANDS).id == expected


def test_bands_are_the_usd_cuts_not_the_stale_aed_ones() -> None:
    """`benchmark-dataset.json` in the source repo is a stale pre-conversion
    copy carrying the AED 2m/10m/30m cuts. Porting from it would put every
    submission in the wrong peer band and be wrong by the 3.6725 peg with
    nothing in the output to show it.
    """
    assert [b.max_usd for b in BANDS] == [545_000, 2_725_000, 8_170_000, None]
    assert all("USD" in b.label for b in BANDS)
    assert not any("AED" in b.label for b in BANDS)


def test_revenue_per_employee_anchors_are_usd_thousands() -> None:
    """The stale JSON has restaurant revEmp at [120, 170, 230, 310, 420] —
    the same figures in thousands of AED."""
    assert tuple(SECTORS["restaurant"].anchors["revEmp"]) == (33, 46, 63, 84, 114)


def test_band_adjustments_apply_to_the_three_size_sensitive_metrics() -> None:
    band = band_for(100_000, BANDS)  # micro: ebitdaAdj -3, revEmpMult 0.8, rentMult 1.25
    assert adjusted_anchors("ebitda", (0, 5, 12, 21, 32), band, mode="sme") == (-3, 2, 9, 18, 29)
    assert adjusted_anchors("revEmp", (100, 200), band, mode="sme") == (80, 160)
    assert adjusted_anchors("rent", (4, 8), band, mode="sme") == (5, 10)
    # Everything else passes through untouched.
    assert adjusted_anchors("gm", (10, 20), band, mode="sme") == (10, 20)


def test_startup_mode_never_applies_a_revenue_band() -> None:
    """The funding stage is already the peer cut there; a revenue band on top
    would double-count size."""
    band = band_for(100_000, BANDS)
    assert adjusted_anchors("ebitda", (0, 5, 12, 21, 32), band, mode="tech") == (0, 5, 12, 21, 32)


@pytest.mark.parametrize(
    "percentile,expected",
    [(1, 1), (24.9, 1), (25, 2), (49.9, 2), (50, 3), (74.9, 3), (75, 4), (99, 4)],
)
def test_quartile_boundaries(percentile: float, expected: int) -> None:
    assert quartile(percentile) == expected


def test_lower_is_better_metrics_are_inverted() -> None:
    """Concentration and premises cost are the two where a high raw figure is
    bad; they must read the same direction as everything else in the score."""
    cut = SECTORS["restaurant"]
    band = band_for(5_000_000, BANDS)
    low_concentration = score_metrics(
        {"conc": cut.anchors["conc"][0]}, specs=SME_METRICS, cut=cut, band=band, mode="sme"
    )[0]["conc"]
    high_concentration = score_metrics(
        {"conc": cut.anchors["conc"][4]}, specs=SME_METRICS, cut=cut, band=band, mode="sme"
    )[0]["conc"]

    assert not SME_METRICS["conc"].higher_is_better
    assert low_concentration.percentile is not None
    assert high_concentration.percentile is not None
    assert low_concentration.percentile > high_concentration.percentile


def test_score_is_weighted_and_reports_covered_weight() -> None:
    """`weight_covered` is how a half-filled form is told apart from a
    genuinely average one — both can score 50."""
    cut = SECTORS["restaurant"]
    band = band_for(5_000_000, BANDS)
    # The value must be compared against the *band-adjusted* anchors — the
    # "mid" band shifts EBITDA anchors by +2, so the raw sector p50 sits
    # below the adjusted p50 and correctly scores under 50.
    adjusted_median = adjusted_anchors("ebitda", cut.anchors["ebitda"], band, mode="sme")[2]
    results, score, covered = score_metrics(
        {"ebitda": adjusted_median}, specs=SME_METRICS, cut=cut, band=band, mode="sme"
    )

    assert score == pytest.approx(50, abs=1)
    assert covered == SME_METRICS["ebitda"].weight
    assert results["gm"].percentile is None


def test_empty_submission_scores_fifty_with_zero_coverage() -> None:
    cut = SECTORS["restaurant"]
    _, score, covered = score_metrics(
        {}, specs=SME_METRICS, cut=cut, band=band_for(0, BANDS), mode="sme"
    )
    assert score == 50.0
    assert covered == 0


def test_sme_metric_weights_sum_to_one_hundred() -> None:
    assert sum(m.weight for m in SME_METRICS.values()) == 100


def test_every_metric_maps_to_a_percentile_column() -> None:
    """Nine `pct_*` columns exist in `seller_roles`; the seven SME metrics
    plus the two tech-only ones must account for exactly those."""
    assert set(SME_METRICS) | set(TECH_METRICS) == set(PERCENTILE_COLUMNS)
    assert len(PERCENTILE_COLUMNS) == 9
    assert len(set(PERCENTILE_COLUMNS.values())) == 9


def test_every_anchor_series_is_ascending_and_five_long() -> None:
    for name, cut in list(SECTORS.items()) + list(STAGES.items()):
        for key, anchors in cut.anchors.items():
            assert len(anchors) == 5, f"{name}.{key}"
            assert list(anchors) == sorted(anchors), f"{name}.{key} not ascending"


def test_dataset_covers_every_sector_and_stage() -> None:
    assert len(SECTORS) == 20
    assert set(STAGES) == {"seed", "seriesa", "seriesb"}
