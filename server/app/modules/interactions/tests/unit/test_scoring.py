from datetime import timedelta

import pytest

from app.modules.interactions.domain.model import ScoringRules, StrengthLabel
from app.modules.interactions.domain.scoring import label_for, score_pair, score_pairs
from app.modules.interactions.tests.fakes.touches import (
    JULES,
    NOW,
    RAMZY,
    email_received,
    email_sent,
    meeting,
)

RULES = ScoringRules()


def _jules_and_sara() -> list:
    """The plan's worked example."""
    return [meeting(10), email_received(20), email_sent(21), email_sent(200)]


def test_worked_example_scores_nine_and_is_strong() -> None:
    touches = _jules_and_sara()

    without_bonus = score_pair(touches, NOW, ScoringRules(two_way_bonus=1.0))
    score = score_pair(touches, NOW, RULES)

    assert without_bonus == pytest.approx(6.05, abs=0.01)
    assert score == pytest.approx(9.08, abs=0.01)
    assert label_for(score, RULES.cutoffs) is StrengthLabel.STRONG


def test_three_quiet_months_drop_the_example_to_good() -> None:
    later = NOW + timedelta(days=90)

    score = score_pair(_jules_and_sara(), later, RULES)

    # Every touch is halved and both emails still sit inside the two-way window.
    assert score == pytest.approx(4.54, abs=0.01)
    assert label_for(score, RULES.cutoffs) is StrengthLabel.GOOD


def test_a_touch_loses_half_its_points_every_half_life() -> None:
    assert score_pair([email_sent(90)], NOW, RULES) == pytest.approx(0.5)
    assert score_pair([email_sent(180)], NOW, RULES) == pytest.approx(0.25)


def test_no_two_way_bonus_when_only_one_side_wrote() -> None:
    assert score_pair([email_sent(0)], NOW, RULES) == pytest.approx(1.0)
    assert score_pair([email_received(0)], NOW, RULES) == pytest.approx(1.5)


def test_no_two_way_bonus_when_one_side_is_outside_the_window() -> None:
    touches = [email_sent(0), email_received(181)]

    expected = 1.0 + 1.5 * 0.5 ** (181 / 90)
    assert score_pair(touches, NOW, RULES) == pytest.approx(expected)


def test_a_meeting_alone_never_earns_the_two_way_bonus() -> None:
    assert score_pair([meeting(0)], NOW, RULES) == pytest.approx(4.0)


def test_future_meetings_do_not_count_yet() -> None:
    assert score_pair([meeting(-5)], NOW, RULES) == 0.0


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (0.0, StrengthLabel.VERY_WEAK),
        (0.99, StrengthLabel.VERY_WEAK),
        (1.0, StrengthLabel.WEAK),
        (2.99, StrengthLabel.WEAK),
        (3.0, StrengthLabel.GOOD),
        (6.99, StrengthLabel.GOOD),
        (7.0, StrengthLabel.STRONG),
        (14.99, StrengthLabel.STRONG),
        (15.0, StrengthLabel.VERY_STRONG),
        (200.0, StrengthLabel.VERY_STRONG),
    ],
)
def test_label_lower_bound_is_inclusive_and_upper_is_exclusive(
    score: float, label: StrengthLabel
) -> None:
    assert label_for(score, RULES.cutoffs) is label


def test_each_team_member_keeps_their_own_strength_with_a_contact() -> None:
    touches = [meeting(1, member=JULES), email_sent(1, member=RAMZY)]

    pairs = score_pairs(touches, NOW, RULES)

    assert [p.team_member for p in pairs] == [JULES, RAMZY]
    assert pairs[0].score > pairs[1].score


def test_equal_scores_sort_by_team_member_name() -> None:
    touches = [email_sent(1, member=RAMZY), email_sent(1, member=JULES)]

    assert [p.team_member for p in score_pairs(touches, NOW, RULES)] == [JULES, RAMZY]
