"""Fakes for exercising the Google clients without the network."""

from collections.abc import Callable

import httpx


class StaticTokenSource:
    """Hands out a token named after the mailbox, and remembers who asked."""

    def __init__(self) -> None:
        self.mailboxes: list[str] = []

    async def token(self, mailbox: str) -> str:
        self.mailboxes.append(mailbox)
        return f"token-for-{mailbox}"


class RecordedSleeps:
    """Stands in for `asyncio.sleep` so retry tests run instantly."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def http_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
