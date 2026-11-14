"""Modals for `/bulk-buyer` and `/bulk-seller`: the file upload form, and the
confirm step shown once a file passed every check.
"""

import uuid

from pydantic import BaseModel
from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import PlainTextObject
from slack_sdk.models.blocks.block_elements import FileInputElement
from slack_sdk.models.views import View

from app.modules.ddl_commands.api.bulk_columns import columns_for, template_filename
from app.modules.ddl_commands.api.bulk_store import UploadKind

UPLOAD_CALLBACK_ID = "bulk_upload_modal"
CONFIRM_CALLBACK_ID = "bulk_confirm_modal"
FILE_BLOCK_ID = "bulk_file"
FILE_ACTION_ID = "file"

_PLURAL = {"buyer": "buyers", "seller": "sellers"}


class BulkUploadMetadata(BaseModel):
    kind: UploadKind
    requested_by: str
    channel_id: str


class BulkConfirmMetadata(BaseModel):
    kind: UploadKind
    preview_id: uuid.UUID
    requested_by: str
    channel_id: str


class SlackFileRef(BaseModel):
    id: str


class FileInputState(BaseModel):
    """What Slack sends back for the file input in a view submission."""

    files: list[SlackFileRef] = []


def modal_title(kind: UploadKind) -> str:
    return f"Bulk add {_PLURAL[kind]}"


def template_url(base_url: str, kind: UploadKind) -> str | None:
    return f"{base_url.rstrip('/')}/{template_filename(kind)}" if base_url else None


def build_bulk_upload_modal(
    kind: UploadKind, *, requested_by: str, channel_id: str, template_link: str | None
) -> View:
    required = ", ".join(f"*{c.label}*" for c in columns_for(kind) if c.required)
    intro = (
        f"Upload a `.csv` or `.xlsx` file with one {kind} per row. Required columns: {required}. "
        "If any row has a problem, nothing is added and you see every problem."
    )
    if template_link:
        intro += f"\n<{template_link}|Download the template>"
    return View(
        type="modal",
        callback_id=UPLOAD_CALLBACK_ID,
        private_metadata=BulkUploadMetadata(
            kind=kind, requested_by=requested_by, channel_id=channel_id
        ).model_dump_json(),
        title=modal_title(kind),
        submit="Check file",
        close="Cancel",
        blocks=[
            SectionBlock(text=intro),
            InputBlock(
                block_id=FILE_BLOCK_ID,
                label=PlainTextObject(text="File"),
                element=FileInputElement(
                    action_id=FILE_ACTION_ID, filetypes=["csv", "xlsx"], max_files=1
                ),
            ),
        ],
    )


def build_checking_modal(kind: UploadKind) -> View:
    return View(
        type="modal",
        title=modal_title(kind),
        close="Cancel",
        blocks=[SectionBlock(text=":hourglass_flowing_sand: _Checking the file…_")],
    )


def build_bulk_confirm_modal(
    kind: UploadKind,
    *,
    new: int,
    existing: int,
    preview_id: uuid.UUID,
    requested_by: str,
    channel_id: str,
) -> View:
    skipped = f" {existing} already in the CRM will be skipped." if existing else ""
    return View(
        type="modal",
        callback_id=CONFIRM_CALLBACK_ID,
        private_metadata=BulkConfirmMetadata(
            kind=kind, preview_id=preview_id, requested_by=requested_by, channel_id=channel_id
        ).model_dump_json(),
        title="Confirm bulk add",
        submit=f"Add {new}"[:24],
        close="Cancel",
        blocks=[
            SectionBlock(
                text=f":white_check_mark: The file is valid. *{new}* new {_PLURAL[kind]} "
                f"will be added.{skipped}"
            )
        ],
    )
