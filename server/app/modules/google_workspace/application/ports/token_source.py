"""Where an access token for one mailbox comes from."""

from typing import Protocol


class TokenSource(Protocol):
    async def token(self, mailbox: str) -> str:
        """A bearer token acting as `mailbox`. Raises if Google refuses the delegation."""
        ...
