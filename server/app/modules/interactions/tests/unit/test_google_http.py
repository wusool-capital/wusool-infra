import httpx
import pytest
from pydantic import BaseModel

from app.modules.interactions.providers.google.http import GoogleApiError, get_model
from app.modules.interactions.tests.fakes.google import (
    RecordedSleeps,
    StaticTokenSource,
    http_client,
)

URL = "https://example.test/things"


class Thing(BaseModel):
    name: str


async def _get(
    *,
    responses: list[httpx.Response],
    sleeps: RecordedSleeps,
    tokens: StaticTokenSource | None = None,
) -> Thing:
    queue = list(responses)
    async with http_client(lambda request: queue.pop(0)) as http:
        return await get_model(
            http, tokens or StaticTokenSource(), "jules@wusoolcapital.com", URL, [], Thing, sleeps
        )


async def test_a_good_reply_is_parsed_into_the_model() -> None:
    sleeps = RecordedSleeps()

    thing = await _get(
        responses=[httpx.Response(200, json={"name": "x", "extra": 1})], sleeps=sleeps
    )

    assert thing == Thing(name="x")
    assert sleeps.calls == []


async def test_the_request_acts_as_the_mailbox_and_carries_its_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"name": "x"})

    tokens = StaticTokenSource()
    async with http_client(handler) as http:
        await get_model(
            http, tokens, "jules@wusoolcapital.com", URL, [("a", "1"), ("a", "2")], Thing
        )

    assert tokens.mailboxes == ["jules@wusoolcapital.com"]
    assert seen[0].headers["authorization"] == "Bearer token-for-jules@wusoolcapital.com"
    assert seen[0].url.params.get_list("a") == ["1", "2"]


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_transient_statuses_are_retried_with_backoff(status: int) -> None:
    sleeps = RecordedSleeps()
    responses = [
        httpx.Response(status),
        httpx.Response(status),
        httpx.Response(200, json={"name": "ok"}),
    ]

    thing = await _get(responses=responses, sleeps=sleeps)

    assert thing.name == "ok"
    assert sleeps.calls == [1.0, 2.0]


async def test_a_rate_limit_sent_as_403_is_retried() -> None:
    sleeps = RecordedSleeps()
    limited = httpx.Response(403, json={"error": {"errors": [{"reason": "userRateLimitExceeded"}]}})

    thing = await _get(responses=[limited, httpx.Response(200, json={"name": "ok"})], sleeps=sleeps)

    assert thing.name == "ok"
    assert sleeps.calls == [1.0]


async def test_an_ordinary_403_is_not_retried() -> None:
    sleeps = RecordedSleeps()
    denied = httpx.Response(403, json={"error": {"errors": [{"reason": "forbidden"}]}})

    with pytest.raises(GoogleApiError) as caught:
        await _get(responses=[denied], sleeps=sleeps)

    assert caught.value.status == 403
    assert sleeps.calls == []


async def test_a_404_is_raised_straight_away_for_the_caller_to_interpret() -> None:
    sleeps = RecordedSleeps()

    with pytest.raises(GoogleApiError) as caught:
        await _get(responses=[httpx.Response(404)], sleeps=sleeps)

    assert caught.value.status == 404
    assert sleeps.calls == []


async def test_a_persistent_failure_gives_up_after_four_attempts() -> None:
    sleeps = RecordedSleeps()

    with pytest.raises(GoogleApiError) as caught:
        await _get(responses=[httpx.Response(500)] * 4, sleeps=sleeps)

    assert caught.value.status == 500
    assert sleeps.calls == [1.0, 2.0, 4.0]
