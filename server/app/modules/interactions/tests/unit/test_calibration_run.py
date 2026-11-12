"""One calibration run end to end with fakes, and the text it prints."""

from collections.abc import Mapping, Sequence
from datetime import timedelta

from app.modules.interactions.application.calibration import CalibrationConfig, run_calibration
from app.modules.interactions.domain.calibration import (
    Bucket,
    CalibrationReport,
    CompanyInput,
    ScoreRow,
)
from app.modules.interactions.domain.linking import RecordDirectory
from app.modules.interactions.domain.model import Channel, ScoringRules, StrengthLabel, Touch
from app.modules.interactions.scripts.calibrate_strength import render, scores_csv
from app.modules.interactions.tests.fakes.touches import JULES, NOW, SARA

RULES = ScoringRules(
    email_sent_points=1.0,
    email_received_points=1.5,
    meeting_points=4.0,
    half_life_days=90.0,
    two_way_bonus=1.5,
    two_way_window_days=180,
    next_window_days=180,
    cutoffs=(1.0, 3.0, 7.0, 15.0),
)
CONFIG = CalibrationConfig(frozenset({JULES}), ("wusoolcapital.com", "dopaminecap.com"), RULES)


class _Source:
    def __init__(self, companies: Sequence[CompanyInput]) -> None:
        self._companies = companies

    async def companies(self) -> Sequence[CompanyInput]:
        return self._companies


class _Reader:
    def __init__(self, touches: Mapping[str, tuple[Touch, ...]]) -> None:
        self._touches = touches

    async def touches_by_organization(self) -> Mapping[str, tuple[Touch, ...]]:
        return self._touches


class _Directory:
    async def load(self) -> RecordDirectory:
        return RecordDirectory({}, {"acme.com": ("o1",), "beta.io": ("o2",)})


def _meetings(count: int) -> tuple[Touch, ...]:
    return tuple(
        Touch(f"m{i}", JULES, SARA, Channel.MEETING, None, NOW - timedelta(days=1 + i))
        for i in range(count)
    )


async def test_our_label_comes_from_the_touches_and_is_compared_with_attios() -> None:
    companies = [
        CompanyInput("c1", ("acme.com",), StrengthLabel.GOOD, "Good", JULES),
        CompanyInput("c2", ("beta.io",), StrengthLabel.STRONG, "Strong", JULES),
    ]
    # Two meetings score about 8, Strong; no touches at all counts o2 as Very weak.
    report = await run_calibration(
        _Source(companies), _Reader({"o1": _meetings(2)}), _Directory(), CONFIG, NOW
    )

    assert (report.compared, report.exact, report.within_one) == (2, 0, 1)
    assert (report.no_interactions, report.excluded) == (1, {})


def test_the_report_names_the_denominator_and_every_left_out_bucket() -> None:
    report = CalibrationReport(
        compared=10,
        exact=8,
        within_one=10,
        matrix=tuple(tuple(0 for _ in range(5)) for _ in range(5)),
        excluded={Bucket.TECH_USER: 3},
    )

    text = render(report)

    assert "Exact match:      8/10 = 80.0%" in text
    assert "Within one level: 10/10 = 100.0%" in text
    assert "Gate: PASS" in text
    assert "    3  Attio's strongest user is tech@" in text
    assert "    0  Attio has no label" in text


def test_a_run_with_nothing_compared_prints_no_percentages() -> None:
    empty = CalibrationReport(0, 0, 0, tuple(tuple(0 for _ in range(5)) for _ in range(5)), {})

    text = render(empty)

    assert "Compared: 0 Companies" in text
    assert "Gate" not in text


def test_the_scores_file_holds_ids_labels_and_numbers_and_a_blank_with_no_interactions() -> None:
    report = CalibrationReport(
        compared=1,
        exact=1,
        within_one=1,
        matrix=tuple(tuple(0 for _ in range(5)) for _ in range(5)),
        excluded={},
        scores=(
            ScoreRow("c1", StrengthLabel.STRONG, 9.0512),
            ScoreRow("c2", StrengthLabel.WEAK, None),
        ),
    )

    assert scores_csv(report) == ("record_id,attio_label,our_score\nc1,Strong,9.0512\nc2,Weak,\n")


def test_the_report_says_how_many_compared_companies_had_no_interactions() -> None:
    report = CalibrationReport(
        compared=5,
        exact=4,
        within_one=5,
        matrix=tuple(tuple(0 for _ in range(5)) for _ in range(5)),
        excluded={},
        no_interactions=3,
    )

    assert "  of which no interactions, counted Very weak: 3" in render(report)
