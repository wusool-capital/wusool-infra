"""A pending report unlock: the gate form, held until the reader proves the
email is theirs by typing back the code we sent to it."""

from dataclasses import dataclass

CODE_LENGTH = 6
MAX_ATTEMPTS = 5


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
    # `time.monotonic()` seconds.
    expires_at: float
    failed_attempts: int = 0
