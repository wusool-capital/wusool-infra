"""Email verification on the report gate: the unlock form only opens a report
once the reader types back a one-time code sent to the address they gave.

Nothing reaches `tool_runs` or Attio until then, so a mistyped or invented
address never becomes a lead.
"""

import hmac
import html
import secrets
import time
from collections.abc import Callable
from dataclasses import replace

from app.modules.lead_magnets.application.shared.ports import UnlockChallengesPort
from app.modules.lead_magnets.domain.insights_report.unlock import (
    CODE_LENGTH,
    MAX_ATTEMPTS,
    ReaderForm,
    UnlockChallenge,
    inbox_key,
)
from app.modules.notifications import EmailSenderPort
from app.modules.utilities import FixedWindowRateLimiter

# Per address: enough for a resend or two, too few to mail-bomb someone else's inbox.
_CODES_PER_EMAIL = 3
_CODES_WINDOW_S = 600


class TooManyCodes(Exception):
    """This address was sent its quota of codes recently."""


class WrongCode(Exception):
    """The code did not match; the reader may try again."""


class ChallengeGone(Exception):
    """Unknown, expired, used up, or for another report: the reader needs a new code."""


class CodeNotSent(Exception):
    """The email provider failed; nothing was stored or counted."""


class ReportUnlock:
    def __init__(
        self,
        *,
        challenges: UnlockChallengesPort,
        mailer: EmailSenderPort,
        email_from: str,
        ttl_s: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._challenges = challenges
        self._mailer = mailer
        self._email_from = email_from
        self._ttl_s = ttl_s
        self._clock = clock
        self._per_email = FixedWindowRateLimiter(limit=_CODES_PER_EMAIL, window_s=_CODES_WINDOW_S)

    async def send_code(self, *, slug: str, report_title: str, form: ReaderForm) -> str:
        """Emails a fresh code and returns the challenge id the page sends back with it."""
        key = inbox_key(form.email)
        now = self._clock()
        if not self._per_email.check(key, now=now):
            raise TooManyCodes
        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        challenge_id = self._challenges.add(
            UnlockChallenge(slug=slug, form=form, code=code, expires_at=now + self._ttl_s),
            now=now,
        )
        try:
            await self._mailer.send(
                to=[form.email],
                from_addr=self._email_from,
                subject=f"Your Wusool report code: {code}",
                body=_code_email(code, report_title, self._ttl_s // 60),
                is_html=True,
            )
        except Exception as exc:
            self._challenges.delete(challenge_id)
            self._per_email.refund(key)
            raise CodeNotSent from exc
        return challenge_id

    def verify(self, *, slug: str, challenge_id: str, code: str) -> ReaderForm:
        """The verified form. The challenge stays until `spend`, so a failed
        save after this still lets the reader retry the same code."""
        challenge = self._challenges.get(challenge_id)
        if (
            challenge is None
            or challenge.slug != slug
            or challenge.expires_at <= self._clock()
            or challenge.failed_attempts >= MAX_ATTEMPTS
        ):
            self._challenges.delete(challenge_id)
            raise ChallengeGone
        if not hmac.compare_digest(challenge.code, code):
            self._challenges.save(
                challenge_id, replace(challenge, failed_attempts=challenge.failed_attempts + 1)
            )
            raise WrongCode
        return challenge.form

    def spend(self, challenge_id: str) -> None:
        """Called once the lead is saved, so the code cannot be replayed."""
        self._challenges.delete(challenge_id)


def _code_email(code: str, report_title: str, ttl_min: int) -> str:
    return (
        '<div style="font-family:Arial,sans-serif;color:#0b1b3f;font-size:15px;line-height:1.5">'
        f"<p>Here is your code to read <strong>{html.escape(report_title)}</strong>:</p>"
        f'<p style="font-size:28px;font-weight:700;letter-spacing:6px">{code}</p>'
        f"<p>It expires in {ttl_min} minutes. If you did not ask for it, ignore this email.</p>"
        "<p>Wusool Capital</p></div>"
    )
