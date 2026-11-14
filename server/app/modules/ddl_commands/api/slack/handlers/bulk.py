"""`/bulk-buyer` and `/bulk-seller`: upload a CSV or Excel file, then either see
every problem (nothing is added) or confirm, and the rows are added in the
background.

Slash commands can't carry files, so the command opens a form with a file input.
Everything after `ack()` runs detached from the HTTP response, so the file is
downloaded and checked while a "checking" view shows, and the result replaces it.
"""

import asyncio
import logging

import aiohttp
from pydantic import BaseModel, ValidationError
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.errors import SlackApiError
from slack_sdk.models.views import View
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.ddl_commands.api.bulk_columns import template_filename
from app.modules.ddl_commands.api.bulk_file import (
    MAX_FILE_BYTES,
    ParsedUpload,
    TemplateError,
    parse_upload,
)
from app.modules.ddl_commands.api.bulk_report import (
    ProblemLine,
    combine_problems,
    errors_csv,
    finished_text,
    has_hidden_problems,
    rejection_text,
)
from app.modules.ddl_commands.api.bulk_store import CommitProgress, UploadKind
from app.modules.ddl_commands.api.bulk_upload import (
    PreviewNotFoundError,
    RejectedUpload,
    commit,
    find_row_problems,
    preview_buyers,
    preview_sellers,
    status,
)
from app.modules.ddl_commands.api.slack.views.bulk_upload_form import (
    CONFIRM_CALLBACK_ID,
    FILE_ACTION_ID,
    FILE_BLOCK_ID,
    UPLOAD_CALLBACK_ID,
    BulkConfirmMetadata,
    BulkUploadMetadata,
    FileInputState,
    build_bulk_confirm_modal,
    build_bulk_upload_modal,
    build_checking_modal,
    modal_title,
    template_url,
)
from app.modules.ddl_commands.config import get_settings
from app.modules.notifications import (
    SlackCommandPayload,
    SlackInteractionBody,
    SlackViewSubmissionPayload,
    build_notice_modal,
)

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 30
_CHUNK_BYTES = 64 * 1024


class _DownloadError(Exception):
    """The file could not be fetched from Slack. The message is safe to show."""


class _SlackFile(BaseModel):
    """The part of Slack's file object this flow reads."""

    name: str = ""
    size: int = 0
    url_private_download: str | None = None
    url_private: str | None = None


async def open_bulk_upload_modal(
    command: SlackCommandPayload, client: AsyncWebClient, *, kind: UploadKind
) -> None:
    link = template_url(get_settings().bulk_template_base_url, kind)
    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_bulk_upload_modal(
            kind,
            requested_by=command["user_id"],
            channel_id=command["channel_id"],
            template_link=link,
        ),
    )


def register(app: AsyncApp) -> None:
    @app.view(UPLOAD_CALLBACK_ID)
    async def handle_upload_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        try:
            metadata = BulkUploadMetadata.model_validate_json(view.get("private_metadata") or "")
        except ValidationError:
            await ack()
            return
        state = FileInputState.model_validate(
            view["state"]["values"].get(FILE_BLOCK_ID, {}).get(FILE_ACTION_ID, {})
        )
        if not state.files:
            await ack(response_action="errors", errors={FILE_BLOCK_ID: "Choose a file to upload."})
            return

        # No database or network call before `ack()`: Slack abandons a view
        # submission after 3s.
        await ack(response_action="update", view=build_checking_modal(metadata.kind))
        try:
            result = await _check_file(client, metadata, state.files[0].id)
        except Exception:
            logger.exception("bulk_upload_check_failed")
            result = build_notice_modal(
                modal_title(metadata.kind),
                "*Something went wrong while checking the file.* Nothing was added. "
                "The error has been logged.",
            )
        await client.views_update(view_id=view["id"], view=result)

    @app.view(CONFIRM_CALLBACK_ID)
    async def handle_confirm_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        await ack()
        try:
            metadata = BulkConfirmMetadata.model_validate_json(view.get("private_metadata") or "")
        except ValidationError:
            return
        requested_by = body["user"]["id"]

        async def say(text: str) -> None:
            await _tell(client, metadata.channel_id, requested_by, text)

        async def on_done(progress: CommitProgress) -> None:
            await say(finished_text(progress))

        expired = "*This upload expired.* Upload the file again."
        try:
            total = status(metadata.preview_id).total
        except PreviewNotFoundError:
            await say(expired)
            return
        # Before `commit`: a small file can finish before this message is sent.
        await say(
            f"Adding {total} {metadata.kind}{'s' if total != 1 else ''}… "
            "I'll post the result here when it finishes."
        )
        try:
            commit(metadata.preview_id, requested_by=requested_by, on_done=on_done)
        except PreviewNotFoundError:
            await say(expired)


async def _tell(client: AsyncWebClient, channel_id: str, user_id: str, text: str) -> None:
    """Best effort. An ephemeral post fails where the bot isn't a member, so fall
    back to a direct message; a failed notice must never undo the work."""
    try:
        await client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
        return
    except SlackApiError:
        logger.warning("bulk_upload_ephemeral_failed", exc_info=True)
    try:
        await client.chat_postMessage(channel=user_id, text=text)
    except SlackApiError:
        logger.warning("bulk_upload_direct_message_failed", exc_info=True)


async def _check_file(client: AsyncWebClient, metadata: BulkUploadMetadata, file_id: str) -> View:
    """The view that replaces the "checking" one."""
    kind, title = metadata.kind, modal_title(metadata.kind)
    try:
        name, content = await _fetch_file(client, file_id)
        # Off the event loop: parsing a large workbook would stall every Slack command.
        parsed = await asyncio.to_thread(parse_upload, kind, name, content)
    except _DownloadError as exc:
        return build_notice_modal(title, f"*Couldn't read the file from Slack.* {exc}")
    except TemplateError as exc:
        return build_notice_modal(title, _wrong_template_text(kind, str(exc)))
    return await _check_rows(client, metadata, parsed)


async def _check_rows(
    client: AsyncWebClient, metadata: BulkUploadMetadata, parsed: ParsedUpload
) -> View:
    kind, title = metadata.kind, modal_title(metadata.kind)
    if parsed.problems:
        # A bad cell rejects the file already; this only gathers the rest, without the database.
        row_problems = find_row_problems(kind, parsed.rows, parsed.lines)
        problems = combine_problems(kind, parsed.problems, row_problems)
        return await _rejected_view(client, metadata, problems)

    preview = preview_buyers if kind == "buyer" else preview_sellers
    result = await preview(parsed.rows, row_numbers=parsed.lines, invoked_via="slack")
    if isinstance(result, RejectedUpload):
        return await _rejected_view(client, metadata, combine_problems(kind, (), result.problems))
    if result.new == 0:
        return build_notice_modal(
            title, f"*Nothing to add.* All {result.existing} rows are already in the CRM."
        )
    return build_bulk_confirm_modal(
        kind,
        new=result.new,
        existing=result.existing,
        preview_id=result.preview_id,
        requested_by=metadata.requested_by,
        channel_id=metadata.channel_id,
    )


async def _rejected_view(
    client: AsyncWebClient, metadata: BulkUploadMetadata, problems: list[ProblemLine]
) -> View:
    if has_hidden_problems(problems):
        await _post_problem_file(client, metadata, problems)
    return build_notice_modal(modal_title(metadata.kind), rejection_text(problems))


async def _post_problem_file(
    client: AsyncWebClient, metadata: BulkUploadMetadata, problems: list[ProblemLine]
) -> None:
    """Best effort: the bot may not be in the channel. The modal still lists the first problems."""
    try:
        await client.files_upload_v2(
            channel=metadata.channel_id,
            filename=f"{metadata.kind}-upload-problems.csv",
            content=errors_csv(problems),
            title="Upload problems",
            initial_comment=(
                f"<@{metadata.requested_by}> all {len(problems)} problems from your "
                f"{metadata.kind} upload. Nothing was added."
            ),
        )
    except SlackApiError:
        logger.warning("bulk_upload_problem_file_failed", exc_info=True)


def _wrong_template_text(kind: UploadKind, reason: str) -> str:
    text = f"*Wrong template format:* {reason}."
    link = template_url(get_settings().bulk_template_base_url, kind)
    if link:
        text += f"\nUse this template: <{link}|{template_filename(kind)}>"
    return text


async def _fetch_file(client: AsyncWebClient, file_id: str) -> tuple[str, bytes]:
    """Needs the `files:read` scope; without it Slack answers with a sign-in page."""
    try:
        info = await client.files_info(file=file_id)
    except SlackApiError:
        raise _DownloadError("Check that the app has the `files:read` permission.") from None
    slack_file = _SlackFile.model_validate(info["file"])
    if slack_file.size > MAX_FILE_BYTES:
        raise TemplateError(f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    url = slack_file.url_private_download or slack_file.url_private
    if url is None:
        raise _DownloadError("Slack gave no download link. Try uploading it again.")

    timeout = aiohttp.ClientTimeout(total=_DOWNLOAD_TIMEOUT_SECONDS)
    headers = {"Authorization": f"Bearer {client.token}"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200 or response.content_type == "text/html":
                    raise _DownloadError("Check that the app has the `files:read` permission.")
                # `read(n)` returns only what is buffered, so read in chunks to the end.
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.content.iter_chunked(_CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_FILE_BYTES:
                        raise TemplateError(
                            f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB"
                        )
                    chunks.append(chunk)
    except (aiohttp.ClientError, TimeoutError):
        raise _DownloadError("The download failed. Try again.") from None
    return slack_file.name, b"".join(chunks)
