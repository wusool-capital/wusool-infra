"""Coverage for the one-search-per-run guard: the run row's discovery claim,
whichever path triggers it (the automatic below-threshold trigger, or the
"Find more sellers" button, which stays clickable after the first search).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.matching_engine.api import dependencies as deps


class _Session:
    async def __aenter__(self) -> SimpleNamespace:
        return SimpleNamespace()

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _service(*, claimed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        claim_discovery=AsyncMock(return_value=claimed),
        finish_discovery=AsyncMock(),
        get_match_analysis=AsyncMock(return_value=None),
    )


async def test_a_run_already_claimed_is_skipped_before_searching(monkeypatch) -> None:
    service = _service(claimed=False)
    notifier = SimpleNamespace(post_message=AsyncMock(), update_message=AsyncMock())
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: _Session)
    monkeypatch.setattr(deps, "matching_engine_service", lambda _session: service)
    monkeypatch.setattr(deps, "_build_slack_notifier", lambda: notifier)

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C_TEST")

    service.get_match_analysis.assert_not_awaited()
    service.finish_discovery.assert_not_awaited()
    notifier.post_message.assert_not_awaited()


async def test_nothing_to_search_releases_the_claim(monkeypatch) -> None:
    service = _service(claimed=True)
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: _Session)
    monkeypatch.setattr(deps, "matching_engine_service", lambda _session: service)

    result = await deps.discover_sellers_for_run(uuid.uuid4())

    assert result.kind == "no_profile"
    assert service.finish_discovery.await_args.kwargs["outcome"] is None
