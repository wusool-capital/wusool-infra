"""Gmail over HTTPS: message headers and labels only, never a body."""

import asyncio
from datetime import UTC, date, datetime

import httpx

from app.modules.interactions.application.errors import CursorExpired
from app.modules.interactions.application.ports.mail_source import MailPage
from app.modules.interactions.application.ports.token_source import TokenSource
from app.modules.interactions.domain.addresses import normalize_address, parse_address_list
from app.modules.interactions.domain.model import MailMessage
from app.modules.interactions.providers.google.http import GoogleApiError, Sleep, get_model
from app.modules.interactions.providers.google.models import (
    GmailHistory,
    GmailList,
    GmailMessage,
    GmailProfile,
)

_BASE = "https://gmail.googleapis.com/gmail/v1/users"
# Asking for these headers only is what keeps bodies out: format=metadata never returns one.
_METADATA_HEADERS = (
    "Message-ID",
    "From",
    "To",
    "Cc",
    "Subject",
    "Auto-Submitted",
    "List-Unsubscribe",
)
_LIST_PAGE_SIZE = "100"
_HISTORY_PAGE_SIZE = "500"
_FETCH_CONCURRENCY = 10


class GmailClient:
    def __init__(
        self, http: httpx.AsyncClient, tokens: TokenSource, sleep: Sleep = asyncio.sleep
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._sleep = sleep

    async def current_history_id(self, mailbox: str) -> str:
        profile = await get_model(
            self._http,
            self._tokens,
            mailbox,
            f"{_BASE}/{mailbox}/profile",
            [],
            GmailProfile,
            self._sleep,
        )
        return profile.history_id

    async def backfill_page(self, mailbox: str, since: date, page_token: str | None) -> MailPage:
        params = [
            ("q", f"after:{since:%Y/%m/%d} -in:chats -in:drafts"),
            ("maxResults", _LIST_PAGE_SIZE),
            *_page_param(page_token),
        ]
        listing = await get_model(
            self._http,
            self._tokens,
            mailbox,
            f"{_BASE}/{mailbox}/messages",
            params,
            GmailList,
            self._sleep,
        )
        messages = await self._fetch(mailbox, [ref.id for ref in listing.messages])
        return MailPage(messages=messages, next_page_token=listing.next_page_token)

    async def changes_page(
        self, mailbox: str, start_history_id: str, page_token: str | None
    ) -> MailPage:
        params = [
            ("startHistoryId", start_history_id),
            ("historyTypes", "messageAdded"),
            ("maxResults", _HISTORY_PAGE_SIZE),
            *_page_param(page_token),
        ]
        try:
            history = await get_model(
                self._http,
                self._tokens,
                mailbox,
                f"{_BASE}/{mailbox}/history",
                params,
                GmailHistory,
                self._sleep,
            )
        except GoogleApiError as error:
            # A bookmark Gmail has dropped answers 404; 410 is accepted too, so a wrong guess
            # about which one it sends re-reads the recent period instead of failing forever.
            if error.status in (404, 410):
                raise CursorExpired(f"Gmail history bookmark expired for {mailbox}") from error
            raise
        added = (item.message.id for record in history.history for item in record.messages_added)
        messages = await self._fetch(mailbox, list(dict.fromkeys(added)))
        return MailPage(
            messages=messages,
            next_page_token=history.next_page_token,
            history_id=history.history_id,
        )

    async def _fetch(self, mailbox: str, message_ids: list[str]) -> tuple[MailMessage, ...]:
        limit = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def one(message_id: str) -> MailMessage | None:
            async with limit:
                return await self._get_message(mailbox, message_id)

        fetched = await asyncio.gather(*(one(message_id) for message_id in message_ids))
        return tuple(message for message in fetched if message is not None)

    async def _get_message(self, mailbox: str, message_id: str) -> MailMessage | None:
        params = [("format", "metadata"), *(("metadataHeaders", h) for h in _METADATA_HEADERS)]
        try:
            raw = await get_model(
                self._http,
                self._tokens,
                mailbox,
                f"{_BASE}/{mailbox}/messages/{message_id}",
                params,
                GmailMessage,
                self._sleep,
            )
        except GoogleApiError as error:
            if error.status == 404:
                return None  # deleted between listing and fetching
            raise
        return _to_message(raw)


def _page_param(page_token: str | None) -> list[tuple[str, str]]:
    return [("pageToken", page_token)] if page_token else []


def _to_message(raw: GmailMessage) -> MailMessage:
    headers: dict[str, str] = {}
    for header in raw.payload.headers:
        headers.setdefault(header.name.lower(), header.value)
    sender = headers.get("from")
    return MailMessage(
        source_id=raw.id,
        thread_id=raw.thread_id,
        message_id=headers.get("message-id", "").strip() or None,
        occurred_at=datetime.fromtimestamp(int(raw.internal_date) / 1000, tz=UTC),
        labels=frozenset(raw.label_ids),
        subject=headers.get("subject"),
        from_address=normalize_address(sender) if sender else None,
        to_addresses=parse_address_list(headers.get("to", "")),
        cc_addresses=parse_address_list(headers.get("cc", "")),
        auto_submitted=headers.get("auto-submitted"),
        has_list_unsubscribe="list-unsubscribe" in headers,
    )
