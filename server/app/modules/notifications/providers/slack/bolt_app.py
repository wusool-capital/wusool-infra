"""Generic Slack Bolt app construction, shared by every module that runs its
own standalone `AsyncApp` (each module's own `api/slack/bolt_app.py` calls
this rather than duplicating the same three lines). Not built at import
time — the caller decides when/whether to construct it (e.g. behind an
`lru_cache`d factory), so the rest of the application can be imported/tested
without Slack credentials present.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from slack_bolt.async_app import AsyncApp, AsyncBoltContext
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.response import BoltResponse
from slack_sdk.models.views import View

from app.modules.notifications.providers.slack.client import NoUnfurlWebClient, guard_view


class GuardedAck(AsyncAck):
    """A `response_action` view skips the client, so `guard_view` runs here too.

    `Any`: forwards the vendor `AsyncAck` arguments unchanged.
    """

    async def __call__(
        self,
        text: str | dict[str, Any] = "",
        *args: Any,
        view: dict[str, Any] | View | None = None,
        **kwargs: Any,
    ) -> BoltResponse:
        if isinstance(view, View):
            view = view.to_dict()
        guarded = guard_view(view) if view is not None else None
        return await super().__call__(text, *args, view=guarded, **kwargs)


async def _install_guarded_ack(
    context: AsyncBoltContext, next_: Callable[[], Awaitable[None]]
) -> None:
    context["ack"] = GuardedAck()
    await next_()


def build_bolt_app(
    bot_token: str, signing_secret: str, register_fn: Callable[[AsyncApp], None]
) -> AsyncApp:
    app = AsyncApp(client=NoUnfurlWebClient(token=bot_token), signing_secret=signing_secret)
    app.middleware(_install_guarded_ack)
    register_fn(app)
    return app
