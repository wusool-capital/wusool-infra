"""The email counterpart to `application/ports/slack.py`'s
`SlackNotifierPort` -- an out-of-band-sending Protocol any module can
depend on. Callers import this, never `boto3`/`providers/ses` directly —
swapping providers later means writing a new implementation of this
Protocol, not touching the caller.
"""

from typing import Protocol


class EmailSenderPort(Protocol):
    async def send(self, *, to: list[str], from_addr: str, subject: str, body: str) -> None: ...
