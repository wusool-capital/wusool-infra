"""Downloading an uploaded file from Slack, against a real local HTTP server."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

import app.modules.ddl_commands.api.slack.handlers.bulk as bulk_handler
from app.modules.ddl_commands.api.bulk_file import MAX_FILE_BYTES, TemplateError

TOKEN = "xoxb-test-token"


@dataclass
class Download:
    body: bytes = b"Organization name,Domain\r\n"
    content_type: str = "text/csv"
    status: int = 200
    seen_auth: list[str] = field(default_factory=list)


@pytest.fixture
async def slack_files() -> AsyncIterator[tuple[TestServer, Download]]:
    download = Download()

    async def handle(request: web.Request) -> web.Response:
        download.seen_auth.append(request.headers.get("Authorization", ""))
        return web.Response(
            body=download.body, status=download.status, content_type=download.content_type
        )

    application = web.Application()
    application.router.add_get("/file", handle)
    server = TestServer(application)
    await server.start_server()
    try:
        yield server, download
    finally:
        await server.close()


def serve_file_info(
    monkeypatch: pytest.MonkeyPatch, server: TestServer, **file: str | int | None
) -> None:
    info = {"name": "list.csv", "size": 10, "url_private_download": str(server.make_url("/file"))}

    async def files_info(self: AsyncWebClient, *, file: str) -> dict[str, dict]:  # noqa: ARG001
        return {"file": {**info, **overrides}}

    overrides = file
    monkeypatch.setattr(AsyncWebClient, "files_info", files_info)


async def test_the_file_is_downloaded_with_the_bots_token(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    serve_file_info(monkeypatch, server)

    name, content = await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")

    assert (name, content) == ("list.csv", download.body)
    assert download.seen_auth == [f"Bearer {TOKEN}"]


async def test_a_file_bigger_than_one_network_chunk_arrives_whole(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    # Several chunks, and below the cap: a short read would silently drop rows.
    download.body = b"Organization name,Domain\r\n" + b"Acme,acme.com\r\n" * 40_000
    serve_file_info(monkeypatch, server, size=len(download.body))

    _, content = await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")

    assert content == download.body
    assert len(content) > 500_000


async def test_a_sign_in_page_means_the_files_read_permission_is_missing(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    download.content_type = "text/html"
    download.body = b"<html>Sign in to Slack</html>"
    serve_file_info(monkeypatch, server)

    with pytest.raises(bulk_handler._DownloadError, match="files:read"):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")


async def test_a_failed_download_status_is_reported(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    download.status = 403
    serve_file_info(monkeypatch, server)

    with pytest.raises(bulk_handler._DownloadError):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")


async def test_slack_refusing_the_file_lookup_means_the_permission_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def files_info(self: AsyncWebClient, *, file: str) -> dict[str, dict]:  # noqa: ARG001
        raise SlackApiError("missing_scope", {"ok": False, "error": "missing_scope"})

    monkeypatch.setattr(AsyncWebClient, "files_info", files_info)

    with pytest.raises(bulk_handler._DownloadError, match="files:read"):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")


async def test_a_file_without_a_download_link_is_reported(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, _ = slack_files
    serve_file_info(monkeypatch, server, url_private_download=None, url_private=None)

    with pytest.raises(bulk_handler._DownloadError, match="no download link"):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")


async def test_a_file_slack_says_is_too_big_is_refused_before_downloading(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    serve_file_info(monkeypatch, server, size=MAX_FILE_BYTES + 1)

    with pytest.raises(TemplateError, match="larger than"):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")

    assert download.seen_auth == []  # never requested


async def test_a_body_bigger_than_the_cap_is_refused_even_if_slack_understated_it(
    monkeypatch: pytest.MonkeyPatch, slack_files: tuple[TestServer, Download]
) -> None:
    server, download = slack_files
    download.body = b"x" * (MAX_FILE_BYTES + 10)
    serve_file_info(monkeypatch, server, size=5)

    with pytest.raises(TemplateError, match="larger than"):
        await bulk_handler._fetch_file(AsyncWebClient(token=TOKEN), "F1")
