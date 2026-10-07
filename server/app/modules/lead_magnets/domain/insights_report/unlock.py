"""A pending report unlock: the gate form, held until the reader proves the
email is theirs by typing back the code we sent to it."""

from dataclasses import dataclass

CODE_LENGTH = 6
MAX_ATTEMPTS = 5
# Providers that ignore dots in the local part.
_DOTLESS_DOMAINS = frozenset({"gmail.com", "googlemail.com"})


@dataclass(frozen=True)
class ReaderForm:
    """The gate's fields, named as `AttioIdentityPayload` reads them back."""

    submission_id: str
    name: str
    company: str
    email: str


@dataclass(frozen=True)
class UnlockChallenge:
    slug: str
    form: ReaderForm
    code: str
    # Seconds on `ReportUnlock`'s clock.
    expires_at: float
    failed_attempts: int = 0


def inbox_key(email: str) -> str:
    """One key per real inbox, so `+tags` and Gmail dots share one code quota."""
    local, _, domain = email.lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in _DOTLESS_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"
