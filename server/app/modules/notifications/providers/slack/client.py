"""One shared `AsyncWebClient`, built once from the bot token — not a full
Bolt `AsyncApp`. `match_dispatch.py`-style out-of-band posting has no live
Bolt-injected `client` to reuse (there's no request in flight), and building
a whole `AsyncApp` just to reach `.client` re-registers every handler for
nothing. Parameterized like `shared/db/session.py`: the token is passed in,
never imported from one specific module's config.
"""

import logging
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from aiohttp import FormData
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

logger = logging.getLogger(__name__)

_MESSAGE_METHODS = frozenset({"chat.postMessage", "chat.update", "chat.postEphemeral"})
_VIEW_METHODS = frozenset({"views.open", "views.update", "views.push", "views.publish"})


def _slack_number(value: str, *, is_decimal_allowed: bool) -> str | None:
    """Slack rejects the whole modal for "12.0" in an integer input, "1.5e+16", or "nan"."""
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    if not is_decimal_allowed:
        # Blank rather than rounded, so the form never shows a number nobody proposed.
        return str(int(number)) if number == number.to_integral_value() else None
    return format(number, "f")


def guard_view(view: dict[str, Any]) -> dict[str, Any]:
    """Rewrites number inputs into a form Slack accepts; blanks any it can't.

    `Any`: raw vendor Block Kit JSON; it never leaves `providers/slack`.
    """
    if "blocks" not in view:
        return view
    blocks: list[dict[str, Any]] = []
    for block in view["blocks"]:
        element = block.get("element") or {}
        value = element.get("initial_value")
        if element.get("type") == "number_input" and value is not None:
            fixed = _slack_number(
                str(value), is_decimal_allowed=bool(element.get("is_decimal_allowed"))
            )
            if fixed is None:
                logger.warning(
                    "Blanked invalid Slack number %r in block %s", value, block.get("block_id")
                )
                element = {k: v for k, v in element.items() if k != "initial_value"}
            else:
                element = {**element, "initial_value": fixed}
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
            metadata = e.response.get("response_metadata") or {}
            if api_method in _VIEW_METHODS and metadata.get("messages"):
                logger.error("Slack rejected %s: %s", api_method, metadata["messages"])
            raise


@lru_cache
def get_slack_client(bot_token: str) -> AsyncWebClient:
    return NoUnfurlWebClient(token=bot_token)
