"""Errors shared by every Attio-first write path (Slack handlers and the
headless seller writer)."""


class PartialWriteError(Exception):
    """Raised when a write fails after one or more earlier steps already
    landed — an org PATCH that succeeded before a role PATCH then failed, an
    org create that succeeded before the role-entry create failed, or an
    Attio write that succeeded before the Postgres write then failed (a
    plain DB error, not the expected `*AlreadyExistsError`). Carries exactly
    what already landed so the Slack message can tell the truth instead of
    assuming nothing was saved.
    """

    def __init__(self, landed: list[str], cause: Exception) -> None:
        self.landed = landed
        self.cause = cause
        super().__init__(str(cause))


def partial_write_message(exc: PartialWriteError) -> str:
    if not exc.landed:
        return f"*Couldn't write to Attio* — nothing was saved. _{exc.cause}_"
    landed_text = "; ".join(exc.landed)
    return f"*Write failed partway through.* Already saved: {landed_text}. _{exc.cause}_"
