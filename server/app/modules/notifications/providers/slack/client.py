"""One shared `AsyncWebClient`, built once from the bot token — not a full
Bolt `AsyncApp`. `match_dispatch.py`-style out-of-band posting has no live
Bolt-injected `client` to reuse (there's no request in flight), and building
a whole `AsyncApp` just to reach `.client` re-registers every handler for
nothing. Parameterized like `shared/db/session.py`: the token is passed in,
never imported from one specific module's config.
"""

from functools import lru_cache

from slack_sdk.web.async_client import AsyncWebClient


@lru_cache
def get_slack_client(bot_token: str) -> AsyncWebClient:
    return AsyncWebClient(token=bot_token)
