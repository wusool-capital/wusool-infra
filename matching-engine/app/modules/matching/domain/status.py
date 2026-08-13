"""The match-result status state machine (§23). Pure, infra-independent:
enforced here in application logic, not relied on via the DB `CHECK`
constraint alone.
"""

from typing import Literal, get_args

MatchStatus = Literal["GENERATED", "PENDING_REVIEW", "APPROVED", "REJECTED", "FAILED"]

ALL_STATUSES: tuple[MatchStatus, ...] = get_args(MatchStatus)

_TERMINAL: frozenset[MatchStatus] = frozenset({"APPROVED", "REJECTED", "FAILED"})

_ALLOWED_TRANSITIONS: dict[MatchStatus, frozenset[MatchStatus]] = {
    "GENERATED": frozenset({"PENDING_REVIEW", "FAILED"}),
    "PENDING_REVIEW": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset(),
    "REJECTED": frozenset(),
    "FAILED": frozenset(),
}


def can_transition(current: MatchStatus, target: MatchStatus) -> bool:
    """No `APPROVED -> GENERATED`, no arbitrary jumps. An action on an
    already-terminal (`APPROVED`/`REJECTED`/`FAILED`) row always fails.
    """
    if current in _TERMINAL:
        return False
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())
