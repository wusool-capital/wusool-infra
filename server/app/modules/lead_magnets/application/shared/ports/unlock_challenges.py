"""Where pending report unlocks wait for their emailed code."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.unlock import UnlockChallenge


class UnlockChallengesPort(Protocol):
    def add(self, challenge: UnlockChallenge) -> str:
        """Returns a fresh, unguessable id for the challenge."""
        ...

    def get(self, challenge_id: str) -> UnlockChallenge | None: ...

    def save(self, challenge_id: str, challenge: UnlockChallenge) -> None: ...

    def delete(self, challenge_id: str) -> None: ...
