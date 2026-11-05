"""One authenticated GET with retries, parsed into a typed model."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

import httpx
from pydantic import BaseModel

from app.modules.google_workspace.application.ports.token_source import TokenSource

_ATTEMPTS = 4
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

Sleep = Callable[[float], Awaitable[None]]


class GoogleApiError(Exception):
    """A non-success reply. Callers map the statuses they expect, such as an expired bookmark."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"Google API returned {status} for {url}")
        self.status = status


def _should_retry(response: httpx.Response) -> bool:
    if response.status_code in _RETRYABLE_STATUSES:
        return True
    # Some quota limits arrive as 403 with a rate-limit reason instead of 429.
    return response.status_code == 403 and b"ateLimitExceeded" in response.content


async def get_model[M: BaseModel](
    http: httpx.AsyncClient,
    tokens: TokenSource,
    mailbox: str,
    url: str,
    params: Sequence[tuple[str, str]],
    model: type[M],
    sleep: Sleep = asyncio.sleep,
) -> M:
    for attempt in range(_ATTEMPTS):
        headers = {"Authorization": f"Bearer {await tokens.token(mailbox)}"}
        response = await http.get(url, params=list(params), headers=headers)
        if response.status_code == 200:
            return model.model_validate_json(response.content)
        if _should_retry(response) and attempt < _ATTEMPTS - 1:
            await sleep(2.0**attempt)
            continue
        raise GoogleApiError(response.status_code, url)
    raise AssertionError("unreachable: the last attempt returns or raises")
