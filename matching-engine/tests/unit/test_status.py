"""§23 state machine tests: no APPROVED -> GENERATED, no arbitrary jumps,
terminal states reject any further action."""

import pytest

from app.modules.matching.domain.status import MatchStatus, can_transition

VALID_TRANSITIONS: list[tuple[MatchStatus, MatchStatus]] = [
    ("GENERATED", "PENDING_REVIEW"),
    ("GENERATED", "FAILED"),
    ("PENDING_REVIEW", "APPROVED"),
    ("PENDING_REVIEW", "REJECTED"),
]

INVALID_TRANSITIONS: list[tuple[MatchStatus, MatchStatus]] = [
    ("APPROVED", "GENERATED"),
    ("APPROVED", "PENDING_REVIEW"),
    ("APPROVED", "REJECTED"),
    ("REJECTED", "APPROVED"),
    ("REJECTED", "GENERATED"),
    ("FAILED", "GENERATED"),
    ("GENERATED", "APPROVED"),  # can't skip PENDING_REVIEW
    ("GENERATED", "REJECTED"),
]


@pytest.mark.parametrize(("current", "target"), VALID_TRANSITIONS)
def test_valid_transitions_allowed(current: MatchStatus, target: MatchStatus) -> None:
    assert can_transition(current, target) is True


@pytest.mark.parametrize(("current", "target"), INVALID_TRANSITIONS)
def test_invalid_transitions_rejected(current: MatchStatus, target: MatchStatus) -> None:
    assert can_transition(current, target) is False


def test_action_on_already_decided_match_leaves_state_unchanged() -> None:
    """An action on an already-APPROVED/REJECTED row must fail cleanly."""
    assert can_transition("APPROVED", "APPROVED") is False
    assert can_transition("REJECTED", "REJECTED") is False
