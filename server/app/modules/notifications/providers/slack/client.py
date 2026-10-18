"""One shared `AsyncWebClient`, built once from the bot token — not a full
Bolt `AsyncApp`. `match_dispatch.py`-style out-of-band posting has no live
Bolt-injected `client` to reuse (there's no request in flight), and building
a whole `AsyncApp` just to reach `.client` re-registers every handler for
nothing. Parameterized like `shared/db/session.py`: the token is passed in,
never imported from one specific module's config.
"""

import logging
import re
from functools import lru_cache
from typing import Any

from aiohttp import FormData
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

logger = logging.getLogger(__name__)

_MESSAGE_METHODS = frozenset({"chat.postMessage", "chat.update", "chat.postEphemeral"})
_VIEW_METHODS = frozenset({"views.open", "views.update", "views.push", "views.publish"})
_INTEGER = re.compile(r"-?\d+")
_DECIMAL = re.compile(r"-?\d+(\.\d+)?")


def guard_view(view: dict[str, Any]) -> dict[str, Any]:
    """Blanks any `number_input` initial value Slack would reject ("12.0" in
    an integer box, "1.5e+16", "nan"): one bad value fails the whole modal
    with `invalid_arguments`. Backstop for every module's forms, behind
    `form_values._number_initial_value`. Returns a copy; never mutates.
    """
    if "blocks" not in view:
        return view
    blocks: list[dict[str, Any]] = []
    for block in view["blocks"]:
        element = block.get("element") or {}
        value = element.get("initial_value")
        if element.get("type") == "number_input" and value is not None:
            pattern = _DECIMAL if element.get("is_decimal_allowed") else _INTEGER
            if not pattern.fullmatch(str(value)):
                logger.warning(
                    "Blanked invalid Slack number %r in block %s", value, block.get("block_id")
                )
                element = {k: v for k, v in element.items() if k != "initial_value"}
                block = {**block, "element": element}
        blocks.append(block)
    return {**view, "blocks": blocks}


class NoUnfurlWebClient(AsyncWebClient):
    """Turns off link/media previews on every message it sends, unless a
    caller sets them explicitly. Source links in our cards would otherwise
    each expand into a large preview, pushing the content off screen.

    Every view it opens, updates, or pushes also goes through `guard_view`.

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
        if api_method in _VIEW_METHODS and json is not None and isinstance(json.get("view"), dict):
            json = {**json, "view": guard_view(json["view"])}
        try:
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
        except SlackApiError as e:
            # Slack's messages name the exact block it rejected; callers only log "failed".
            if api_method in _VIEW_METHODS:
                metadata = e.response.get("response_metadata") or {}
                logger.error("Slack rejected %s: %s", api_method, metadata.get("messages"))
            raise


@lru_cache
def get_slack_client(bot_token: str) -> AsyncWebClient:
    return NoUnfurlWebClient(token=bot_token)
