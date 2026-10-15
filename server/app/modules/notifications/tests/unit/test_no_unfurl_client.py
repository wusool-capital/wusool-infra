"""Source links in posted cards must never expand into big previews."""

from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.notifications.providers.slack.client import NoUnfurlWebClient


@pytest.mark.parametrize("method", ["chat.postMessage", "chat.update", "chat.postEphemeral"])
async def test_message_calls_disable_previews(method: str) -> None:
    with patch.object(AsyncWebClient, "api_call", new_callable=AsyncMock) as base:
        await NoUnfurlWebClient(token="x").api_call(method, json={"text": "hi"})

    sent = base.call_args.kwargs["json"]
    assert sent == {"text": "hi", "unfurl_links": False, "unfurl_media": False}


async def test_explicit_caller_choice_wins_and_other_methods_are_untouched() -> None:
    client = NoUnfurlWebClient(token="x")
    with patch.object(AsyncWebClient, "api_call", new_callable=AsyncMock) as base:
        await client.api_call("chat.update", json={"unfurl_links": True})
        await client.api_call("views.open", json={"trigger_id": "t"})

    assert base.call_args_list[0].kwargs["json"]["unfurl_links"] is True
    assert base.call_args_list[1].kwargs["json"] == {"trigger_id": "t"}
