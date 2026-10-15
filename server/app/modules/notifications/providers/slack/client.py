"""One shared `AsyncWebClient`, built once from the bot token — not a full
Bolt `AsyncApp`. `match_dispatch.py`-style out-of-band posting has no live
Bolt-injected `client` to reuse (there's no request in flight), and building
a whole `AsyncApp` just to reach `.client` re-registers every handler for
nothing. Parameterized like `shared/db/session.py`: the token is passed in,
never imported from one specific module's config.
"""

from functools import lru_cache
from typing import Any

from aiohttp import FormData
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

_MESSAGE_METHODS = frozenset({"chat.postMessage", "chat.update", "chat.postEphemeral"})


class NoUnfurlWebClient(AsyncWebClient):
    """Turns off link/media previews on every message it sends, unless a
    caller sets them explicitly. Source links in our cards would otherwise
    each expand into a large preview, pushing the content off screen.

    The `Any` payloads mirror the vendor SDK's own override signature; they
    never leave this provider class.
    """

    async def api_call(
        self,
        api_method: str,
        *,
        http_verb: str = "POST",
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | FormData | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        auth: dict[str, Any] | None = None,
    ) -> AsyncSlackResponse:
        if api_method in _MESSAGE_METHODS and json is not None:
            json = {"unfurl_links": False, "unfurl_media": False, **json}
        return await super().api_call(
            api_method,
            http_verb=http_verb,
            files=files,
            data=data,
            params=params,
            json=json,
            headers=headers,
            auth=auth,
        )


@lru_cache
def get_slack_client(bot_token: str) -> AsyncWebClient:
    return NoUnfurlWebClient(token=bot_token)
