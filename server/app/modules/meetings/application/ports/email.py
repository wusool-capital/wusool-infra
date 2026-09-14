"""The provider-agnostic seam `api/feedback.py` depends on. Callers import
this Protocol, never `boto3`/`app.modules.meetings.providers.ses` directly —
swapping providers later means writing a new implementation of this
Protocol, not touching the endpoint.
"""

from typing import Protocol


class EmailSenderPort(Protocol):
    async def send(self, *, to: list[str], from_addr: str, subject: str, body: str) -> None: ...
