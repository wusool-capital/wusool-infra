from datetime import UTC, date, datetime

import httpx
import pytest

from app.modules.google_workspace.application.errors import CursorExpired
from app.modules.google_workspace.providers.google.gmail import GmailClient
from app.modules.google_workspace.providers.google.http import GoogleApiError
from app.modules.google_workspace.tests.fakes.google import (
    RecordedSleeps,
    StaticTokenSource,
    http_client,
)

MAILBOX = "jules@wusoolcapital.com"
SENT_AT = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
USERS = f"/gmail/v1/users/{MAILBOX}"


def _message(message_id: str, headers: list[tuple[str, str]], labels: tuple[str, ...] = ("INBOX",)):
    return {
        "id": message_id,
        "threadId": f"t-{message_id}",
        "labelIds": list(labels),
        "internalDate": str(int(SENT_AT.timestamp() * 1000)),
        "payload": {"headers": [{"name": n, "value": v} for n, v in headers]},
    }


class _Gmail:
    """Routes Gmail paths to canned JSON and records every request."""

    def __init__(self, routes: dict[str, httpx.Response]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        # /gmail/v1/users/<mailbox>/<route...>
        return self.routes["/" + "/".join(request.url.path.split("/")[5:])]


def _client(http: httpx.AsyncClient, sleeps: RecordedSleeps) -> GmailClient:
    return GmailClient(http, StaticTokenSource(), sleeps)


async def test_current_history_id_reads_the_profile() -> None:
    gmail = _Gmail(
        {"/profile": httpx.Response(200, json={"historyId": "777", "emailAddress": MAILBOX})}
    )
    async with http_client(gmail) as http:
        assert await _client(http, RecordedSleeps()).current_history_id(MAILBOX) == "777"


async def test_backfill_lists_by_date_then_fetches_each_message_as_metadata() -> None:
    gmail = _Gmail(
        {
            "/messages": httpx.Response(
                200,
                json={
                    "messages": [
                        {"id": "m1", "threadId": "t-m1"},
                        {"id": "m2", "threadId": "t-m2"},
                    ],
                    "nextPageToken": "page-2",
                },
            ),
            "/messages/m1": httpx.Response(
                200,
                json=_message(
                    "m1",
                    [
                        ("Message-ID", " <abc@mail.acme.com> "),
                        ("From", "Sara Lee <Sara@Acme.COM>"),
                        ("To", '"Chasles, Jules" <jules@wusoolcapital.com>, ramzy@dopaminecap.com'),
                        ("Cc", "legal@acme.com"),
                        ("Subject", "Term sheet"),
                        ("List-Unsubscribe", "<mailto:x@acme.com>"),
                        ("Auto-Submitted", "auto-generated"),
                    ],
                    labels=("INBOX", "IMPORTANT"),
                ),
            ),
            "/messages/m2": httpx.Response(200, json=_message("m2", [("Subject", "Plain")])),
        }
    )
    async with http_client(gmail) as http:
        page = await _client(http, RecordedSleeps()).backfill_page(MAILBOX, date(2025, 11, 5), None)

    listing = gmail.requests[0].url.params
    assert listing["q"] == "after:2025/11/05 -in:chats -in:drafts"
    assert "pageToken" not in listing
    first, second = sorted(page.messages, key=lambda m: m.source_id)
    assert page.next_page_token == "page-2"
    assert first.message_id == "<abc@mail.acme.com>"
    assert first.thread_id == "t-m1"
    assert first.occurred_at == SENT_AT
    assert first.labels == frozenset({"INBOX", "IMPORTANT"})
    assert first.subject == "Term sheet"
    assert first.from_address == "sara@acme.com"
    assert first.to_addresses == ("jules@wusoolcapital.com", "ramzy@dopaminecap.com")
    assert first.cc_addresses == ("legal@acme.com",)
    assert first.auto_submitted == "auto-generated"
    assert first.has_list_unsubscribe is True
    assert (second.message_id, second.from_address, second.to_addresses) == (None, None, ())
    assert second.has_list_unsubscribe is False


async def test_each_fetch_asks_for_metadata_and_only_the_wanted_headers() -> None:
    gmail = _Gmail(
        {
            "/messages": httpx.Response(200, json={"messages": [{"id": "m1", "threadId": "t"}]}),
            "/messages/m1": httpx.Response(200, json=_message("m1", [])),
        }
    )
    async with http_client(gmail) as http:
        await _client(http, RecordedSleeps()).backfill_page(MAILBOX, date(2025, 11, 5), "p9")

    fetch = gmail.requests[1].url.params
    assert gmail.requests[0].url.params["pageToken"] == "p9"
    assert fetch["format"] == "metadata"
    assert fetch.get_list("metadataHeaders") == [
        "Message-ID",
        "From",
        "To",
        "Cc",
        "Subject",
        "Auto-Submitted",
        "List-Unsubscribe",
    ]


async def test_a_message_deleted_before_it_is_fetched_is_skipped() -> None:
    gmail = _Gmail(
        {
            "/messages": httpx.Response(
                200,
                json={"messages": [{"id": "m1", "threadId": "t"}, {"id": "gone", "threadId": "t"}]},
            ),
            "/messages/m1": httpx.Response(200, json=_message("m1", [("Subject", "Kept")])),
            "/messages/gone": httpx.Response(404),
        }
    )
    async with http_client(gmail) as http:
        page = await _client(http, RecordedSleeps()).backfill_page(MAILBOX, date(2025, 11, 5), None)

    assert [m.source_id for m in page.messages] == ["m1"]


async def test_the_first_value_of_a_repeated_header_wins() -> None:
    gmail = _Gmail(
        {
            "/messages": httpx.Response(200, json={"messages": [{"id": "m1", "threadId": "t"}]}),
            "/messages/m1": httpx.Response(
                200, json=_message("m1", [("Subject", "First"), ("subject", "Second")])
            ),
        }
    )
    async with http_client(gmail) as http:
        page = await _client(http, RecordedSleeps()).backfill_page(MAILBOX, date(2025, 11, 5), None)

    assert page.messages[0].subject == "First"


async def test_changes_fetch_each_added_message_once_and_return_the_new_bookmark() -> None:
    history = {
        "history": [
            {"messagesAdded": [{"message": {"id": "m1", "threadId": "t"}}]},
            {
                "labelsAdded": [],
                "messagesAdded": [
                    {"message": {"id": "m1", "threadId": "t"}},
                    {"message": {"id": "m2", "threadId": "t"}},
                ],
            },
        ],
        "nextPageToken": "more",
        "historyId": "900",
    }
    gmail = _Gmail(
        {
            "/history": httpx.Response(200, json=history),
            "/messages/m1": httpx.Response(200, json=_message("m1", [])),
            "/messages/m2": httpx.Response(200, json=_message("m2", [])),
        }
    )
    async with http_client(gmail) as http:
        page = await _client(http, RecordedSleeps()).changes_page(MAILBOX, "800", None)

    params = gmail.requests[0].url.params
    assert (params["startHistoryId"], params["historyTypes"]) == ("800", "messageAdded")
    assert sorted(m.source_id for m in page.messages) == ["m1", "m2"]
    assert sum(r.url.path.endswith("/messages/m1") for r in gmail.requests) == 1
    assert (page.history_id, page.next_page_token) == ("900", "more")


async def test_an_empty_history_still_returns_the_bookmark() -> None:
    gmail = _Gmail({"/history": httpx.Response(200, json={"historyId": "901"})})
    async with http_client(gmail) as http:
        page = await _client(http, RecordedSleeps()).changes_page(MAILBOX, "800", None)

    assert (page.messages, page.history_id, page.next_page_token) == ((), "901", None)


async def test_a_dropped_bookmark_raises_cursor_expired() -> None:
    gmail = _Gmail({"/history": httpx.Response(404)})
    async with http_client(gmail) as http:
        with pytest.raises(CursorExpired):
            await _client(http, RecordedSleeps()).changes_page(MAILBOX, "1", None)


async def test_any_other_history_failure_is_not_mistaken_for_an_expired_bookmark() -> None:
    gmail = _Gmail({"/history": httpx.Response(403, json={"error": "forbidden"})})
    async with http_client(gmail) as http:
        with pytest.raises(GoogleApiError) as caught:
            await _client(http, RecordedSleeps()).changes_page(MAILBOX, "1", None)

    assert caught.value.status == 403


async def test_transient_errors_are_retried_before_giving_up() -> None:
    replies = [httpx.Response(503), httpx.Response(200, json={"historyId": "5"})]
    sleeps = RecordedSleeps()

    async with http_client(lambda request: replies.pop(0)) as http:
        assert (
            await GmailClient(http, StaticTokenSource(), sleeps).current_history_id(MAILBOX) == "5"
        )

    assert sleeps.calls == [1.0]


class _FrozenClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _backfill_of(count: int) -> _Gmail:
    ids = [f"m{i}" for i in range(count)]
    listing = {"messages": [{"id": i, "threadId": "t"} for i in ids]}
    routes = {"/messages": httpx.Response(200, json=listing)}
    routes.update({f"/messages/{i}": httpx.Response(200, json=_message(i, [])) for i in ids})
    return _Gmail(routes)


async def test_message_fetches_are_spaced_to_stay_under_the_mailbox_quota() -> None:
    gmail = _backfill_of(4)
    sleeps = RecordedSleeps()

    async with http_client(gmail) as http:
        client = GmailClient(http, StaticTokenSource(), sleeps, _FrozenClock())
        page = await client.backfill_page(MAILBOX, date(2025, 11, 5), None)

    assert len(page.messages) == 4
    # 250 fetches a minute is one every 0.24s: the first goes at once, the rest queue behind it.
    assert sorted(sleeps.calls) == pytest.approx([0.24, 0.48, 0.72])


async def test_the_pace_is_kept_per_mailbox() -> None:
    gmail = _backfill_of(1)
    sleeps = RecordedSleeps()
    other = "ramzy@wusoolcapital.com"

    async with http_client(gmail) as http:
        client = GmailClient(http, StaticTokenSource(), sleeps, _FrozenClock())
        await client._get_message(MAILBOX, "m0")
        await client._get_message(other, "m0")
        # A second fetch for the first mailbox is the one that has to queue.
        await client._get_message(MAILBOX, "m0")

    assert sleeps.calls == pytest.approx([0.24])


async def test_a_fetch_after_the_slot_has_passed_does_not_wait() -> None:
    gmail = _backfill_of(1)
    sleeps = RecordedSleeps()
    clock = _FrozenClock()

    async with http_client(gmail) as http:
        client = GmailClient(http, StaticTokenSource(), sleeps, clock)
        await client._get_message(MAILBOX, "m0")
        clock.now += 1.0
        await client._get_message(MAILBOX, "m0")

    assert sleeps.calls == []
