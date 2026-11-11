"""Reads Gmail and Calendar metadata for the team mailboxes and computes the
Attio relationship fields (last and next interaction, connection strength).

Read-only so far: nothing here writes to Attio. The scoring and summary rules
live in `domain/` as pure functions; `InteractionsSettings` holds every tunable.

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.interactions.domain.model import (
    Channel,
    Direction,
    InteractionSummary,
    Role,
    ScoringRules,
    StrengthLabel,
    Touch,
)
from app.modules.interactions.domain.scoring import label_for, score_pair
from app.modules.interactions.domain.summary import summarize

__all__ = [
    "Channel",
    "Direction",
    "InteractionSummary",
    "Role",
    "ScoringRules",
    "StrengthLabel",
    "Touch",
    "label_for",
    "score_pair",
    "summarize",
]
