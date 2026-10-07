"""In-process store for pending report unlocks.

One toolkit container runs per environment, so a dict is accurate. A deploy
drops codes in flight; those readers just ask for a new one.
"""

import secrets
import time

from app.modules.lead_magnets.domain.insights_report.unlock import UnlockChallenge


class InMemoryUnlockChallenges:
    def __init__(self) -> None:
        self._challenges: dict[str, UnlockChallenge] = {}

    def add(self, challenge: UnlockChallenge) -> str:
        self._evict_expired()
        challenge_id = secrets.token_urlsafe(24)
        self._challenges[challenge_id] = challenge
        return challenge_id

    def get(self, challenge_id: str) -> UnlockChallenge | None:
        return self._challenges.get(challenge_id)

    def save(self, challenge_id: str, challenge: UnlockChallenge) -> None:
        self._challenges[challenge_id] = challenge

    def delete(self, challenge_id: str) -> None:
        self._challenges.pop(challenge_id, None)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        for challenge_id in [k for k, c in self._challenges.items() if c.expires_at <= now]:
            del self._challenges[challenge_id]
