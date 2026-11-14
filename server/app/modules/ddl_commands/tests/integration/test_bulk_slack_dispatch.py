"""`/bulk-buyer` and `/bulk-seller` through Bolt, signed the way Slack signs a
request. No database and no Slack network: the file download, the organization
lookups and the Slack Web API calls are faked.
"""

import asyncio
import csv
import io
import uuid
from types import SimpleNamespace

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.models.views import View

import app.modules.ddl_commands.api.bulk_upload as bulk_upload_module
import app.modules.ddl_commands.api.slack.handlers.bulk as bulk_handler
from app.modules.ddl_commands.api.bulk_columns import columns_for
from app.modules.ddl_commands.api.bulk_store import (
    CommitProgress,
    InMemoryPreviewStore,
    RowOutcome,
    UploadKind,
)
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.slack.views.bulk_upload_form import (
    BulkConfirmMetadata,
    BulkUploadMetadata,
)
from app.modules.ddl_commands.bootstrap import create_app
from app.modules.ddl_commands.config import get_settings
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral, post_slack_command
from tests.slack_test_helpers import post_interactivity as _shared_post_interactivity

app = create_app()
VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[0]
TEMPLATE_BASE = "https://assets.example.test/templates"


def _post_interactivity(payload: dict) -> object:
    return _shared_post_interactivity(app, get_settings().slack_signing_secret, payload)


def _label(kind: UploadKind, field: str) -> str:
    return next(c.label for c in columns_for(kind) if c.field == field)


HEADER = [_label("buyer", f) for f in ("org_name", "domain", "target_vertical")]


def _csv(header: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _as_dict(view: View | dict) -> dict:
    return view if isinstance(view, dict) else view.to_dict()


def _text(view: View | dict) -> str:
    blocks = _as_dict(view)["blocks"]
    return "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")


@pytest.fixture(autouse=True)
def slack(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    calls = SimpleNamespace(
        posted=mock_slack_ephemeral(monkeypatch), opened=[], updated=[], uploaded=[], lookups=0
    )
    mock_slack_auth(monkeypatch)

    async def views_open(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        calls.opened.append(kwargs)
        return {"view": {"id": "V1"}}

    async def views_update(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        calls.updated.append(kwargs)
        return {"ok": True}

    async def files_upload_v2(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        calls.uploaded.append(kwargs)
        return {"ok": True}

    base = "slack_sdk.web.async_client.AsyncWebClient"
    monkeypatch.setattr(f"{base}.views_open", views_open)
    monkeypatch.setattr(f"{base}.views_update", views_update)
    monkeypatch.setattr(f"{base}.files_upload_v2", files_upload_v2)

    monkeypatch.setattr(bulk_upload_module, "_store", InMemoryPreviewStore())

    async def no_org(hosts: list[str]) -> None:
        calls.lookups += 1

    monkeypatch.setattr(bulk_upload_module, "find_organization_by_domains", no_org)
    monkeypatch.setattr(get_settings(), "bulk_template_base_url", TEMPLATE_BASE)
    return calls


def _serve_file(monkeypatch: pytest.MonkeyPatch, content: bytes, name: str = "list.csv") -> None:
    async def fetch(client, file_id):  # noqa: ANN001, ANN202
        return name, content

    monkeypatch.setattr(bulk_handler, "_fetch_file", fetch)


def _upload_payload(kind: UploadKind = "buyer", file_ids: tuple[str, ...] = ("F1",)) -> dict:
    metadata = BulkUploadMetadata(kind=kind, requested_by="U_TEST", channel_id="C_TEST")
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V1",
            "callback_id": "bulk_upload_modal",
            "private_metadata": metadata.model_dump_json(),
            "state": {
                "values": {
                    "bulk_file": {
                        "file": {"type": "file_input", "files": [{"id": f} for f in file_ids]}
                    }
                }
            },
        },
    }


def _confirm_payload(preview_id: uuid.UUID, submitter: str = "U_TEST") -> dict:
    metadata = BulkConfirmMetadata(
        kind="buyer", preview_id=preview_id, requested_by="U_SOMEONE_ELSE", channel_id="C_TEST"
    )
    return {
        "type": "view_submission",
        "user": {"id": submitter},
        "view": {
            "type": "modal",
            "id": "V2",
            "callback_id": "bulk_confirm_modal",
            "private_metadata": metadata.model_dump_json(),
            "state": {"values": {}},
        },
    }


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_the_command_opens_the_upload_form(kind: UploadKind, slack: SimpleNamespace) -> None:
    response = post_slack_command(app, get_settings().slack_signing_secret, command=f"/bulk-{kind}")

    assert response.status_code == 200
    assert slack.opened[0]["trigger_id"] == "trigger.123"
    view = _as_dict(slack.opened[0]["view"])
    assert view["callback_id"] == "bulk_upload_modal"
    assert view["title"]["text"] == f"Bulk add {kind}s"
    file_input = next(b for b in view["blocks"] if b["type"] == "input")["element"]
    assert file_input["type"] == "file_input"
    assert file_input["filetypes"] == ["csv", "xlsx"]
    assert file_input["max_files"] == 1
    assert f"<{TEMPLATE_BASE}/{kind}-template.csv|Download the template>" in _text(view)
    assert BulkUploadMetadata.model_validate_json(view["private_metadata"]).kind == kind


def test_the_form_has_no_download_link_when_no_template_is_configured(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    monkeypatch.setattr(get_settings(), "bulk_template_base_url", "")

    post_slack_command(app, get_settings().slack_signing_secret, command="/bulk-buyer")

    assert "Download the template" not in _text(slack.opened[0]["view"])


def test_submitting_without_a_file_asks_for_one(slack: SimpleNamespace) -> None:
    response = _post_interactivity(_upload_payload(file_ids=()))

    assert response.json() == {
        "response_action": "errors",
        "errors": {"bulk_file": "Choose a file to upload."},
    }
    assert slack.updated == []


def test_the_submission_is_acknowledged_with_a_checking_view_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve_file(monkeypatch, _csv(HEADER, [["Acme", "acme.com", VERTICAL]]))

    response = _post_interactivity(_upload_payload())

    body = response.json()
    assert body["response_action"] == "update"
    assert "Checking the file" in _text(body["view"])


def test_a_clean_file_shows_the_confirm_step_and_stores_the_new_rows(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    _serve_file(
        monkeypatch, _csv(HEADER, [["Acme", "acme.com", VERTICAL], ["Beta", "beta.com", VERTICAL]])
    )

    _post_interactivity(_upload_payload())

    assert slack.updated[0]["view_id"] == "V1"
    view = _as_dict(slack.updated[0]["view"])
    assert view["callback_id"] == "bulk_confirm_modal"
    assert view["submit"]["text"] == "Add 2"
    metadata = BulkConfirmMetadata.model_validate_json(view["private_metadata"])
    stored = bulk_upload_module._store.get(metadata.preview_id)
    assert stored is not None
    assert stored.invoked_via == "slack"
    assert [r.index for r in stored.rows] == [2, 3]  # spreadsheet lines


def test_companies_already_in_the_crm_are_skipped_not_rejected(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    async def existing_org(hosts: list[str]) -> SimpleNamespace | None:
        return SimpleNamespace(attio_id="org-1") if "acme.com" in hosts else None

    async def buyer_exists(org_attio_id: str, vertical: str | None) -> bool:
        return True

    monkeypatch.setattr(bulk_upload_module, "find_organization_by_domains", existing_org)
    monkeypatch.setattr(
        bulk_upload_module,
        "ddl_commands_service",
        lambda: SimpleNamespace(buyer_exists=buyer_exists),
    )
    _serve_file(
        monkeypatch, _csv(HEADER, [["Acme", "acme.com", VERTICAL], ["Beta", "beta.com", VERTICAL]])
    )

    _post_interactivity(_upload_payload())

    view = _as_dict(slack.updated[0]["view"])
    assert view["submit"]["text"] == "Add 1"
    assert "1 already in the CRM will be skipped" in _text(view)


def test_a_file_of_only_existing_companies_has_nothing_to_add(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    async def existing_org(hosts: list[str]) -> SimpleNamespace:
        return SimpleNamespace(attio_id="org-1")

    async def buyer_exists(org_attio_id: str, vertical: str | None) -> bool:
        return True

    monkeypatch.setattr(bulk_upload_module, "find_organization_by_domains", existing_org)
    monkeypatch.setattr(
        bulk_upload_module,
        "ddl_commands_service",
        lambda: SimpleNamespace(buyer_exists=buyer_exists),
    )
    _serve_file(monkeypatch, _csv(HEADER, [["Acme", "acme.com", VERTICAL]]))

    _post_interactivity(_upload_payload())

    assert "*Nothing to add.* All 1 rows are already in the CRM." in _text(slack.updated[0]["view"])


def test_one_bad_row_rejects_the_whole_file_and_nothing_is_stored_or_looked_up(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    rows = [
        ["Acme", "acme.com", VERTICAL],
        ["Beta", "beta.com", "Not a vertical"],
        ["Gamma", "gamma.com", VERTICAL],
    ]
    _serve_file(monkeypatch, _csv(HEADER, rows))

    _post_interactivity(_upload_payload())

    view = _as_dict(slack.updated[0]["view"])
    assert view.get("callback_id") != "bulk_confirm_modal"
    text = _text(view)
    assert "*Nothing was added.* 1 problem in 1 row." in text
    assert "Line 3, Target vertical: not an allowed value" in text
    assert slack.lookups == 0
    assert slack.uploaded == []


def test_problems_found_in_the_row_checks_are_reported_too(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    rows = [
        ["Acme", "acme.com", VERTICAL],
        ["", "beta.com", VERTICAL],
        ["Acme again", "acme.com", VERTICAL],
    ]
    _serve_file(monkeypatch, _csv(HEADER, rows))

    _post_interactivity(_upload_payload())

    text = _text(slack.updated[0]["view"])
    assert "Line 3, Organization name: is required" in text
    assert "Line 4: same company as line 2" in text
    assert slack.lookups == 0


def test_the_wrong_template_message_names_the_reason_and_links_the_template(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    _serve_file(monkeypatch, _csv([*HEADER, "Surprise"], [["Acme", "acme.com", VERTICAL, ""]]))

    _post_interactivity(_upload_payload())

    text = _text(slack.updated[0]["view"])
    assert text == (
        "*Wrong template format:* unknown columns: Surprise.\n"
        f"Use this template: <{TEMPLATE_BASE}/buyer-template.csv|buyer-template.csv>"
    )


def test_the_wrong_template_message_works_without_a_configured_link(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    monkeypatch.setattr(get_settings(), "bulk_template_base_url", "")
    _serve_file(monkeypatch, b"", name="list.csv")

    _post_interactivity(_upload_payload())

    assert _text(slack.updated[0]["view"]) == "*Wrong template format:* the file is empty."


def test_a_seller_file_does_not_need_a_vertical(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    header = [_label("seller", "org_name"), _label("seller", "domain")]
    _serve_file(monkeypatch, _csv(header, [["Acme", "acme.com"]]))

    _post_interactivity(_upload_payload(kind="seller"))

    assert _as_dict(slack.updated[0]["view"])["callback_id"] == "bulk_confirm_modal"


def test_more_than_twenty_problems_also_attach_the_full_list(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    rows = [["", f"co{n}.com", VERTICAL] for n in range(25)]
    _serve_file(monkeypatch, _csv(HEADER, rows))

    _post_interactivity(_upload_payload())

    text = _text(slack.updated[0]["view"])
    assert text.count("• ") == 20
    assert "_…and 5 more._" in text
    upload = slack.uploaded[0]
    assert upload["channel"] == "C_TEST"
    assert upload["filename"] == "buyer-upload-problems.csv"
    attached = list(csv.reader(io.StringIO(upload["content"].decode("utf-8-sig"))))
    assert len(attached) == 1 + 25
    assert attached[1][:2] == ["2", "Organization name"]


def test_a_few_long_problems_also_attach_the_full_list_when_the_message_cannot_fit_them(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    rows = [[f"Co {n}", f"co{n}.com", "Not a vertical"] for n in range(15)]
    _serve_file(monkeypatch, _csv(HEADER, rows))

    _post_interactivity(_upload_payload())

    assert "more._" in _text(slack.updated[0]["view"])  # fewer than 20 problems, still cut
    attached = list(csv.reader(io.StringIO(slack.uploaded[0]["content"].decode("utf-8-sig"))))
    assert len(attached) == 1 + 15


def test_the_problems_still_show_when_the_full_list_cannot_be_attached(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    async def not_in_channel(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise SlackApiError("not_in_channel", {"ok": False, "error": "not_in_channel"})

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.files_upload_v2", not_in_channel)
    rows = [[f"Co {n}", f"co{n}.com", "Not a vertical"] for n in range(25)]
    _serve_file(monkeypatch, _csv(HEADER, rows))

    _post_interactivity(_upload_payload())

    assert "*Nothing was added.* 25 problems" in _text(slack.updated[0]["view"])


def test_a_download_failure_is_explained_and_nothing_is_added(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    async def fail(client, file_id):  # noqa: ANN001, ANN202
        raise bulk_handler._DownloadError("Check that the app has the `files:read` permission.")

    monkeypatch.setattr(bulk_handler, "_fetch_file", fail)

    _post_interactivity(_upload_payload())

    text = _text(slack.updated[0]["view"])
    assert text.startswith("*Couldn't read the file from Slack.*")
    assert "files:read" in text


def test_an_unexpected_error_is_reported_and_nothing_is_added(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    _serve_file(monkeypatch, _csv(HEADER, [["Acme", "acme.com", VERTICAL]]))

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(bulk_handler, "parse_upload", boom)

    _post_interactivity(_upload_payload())

    text = _text(slack.updated[0]["view"])
    assert text.startswith("*Something went wrong while checking the file.* Nothing was added.")
    assert "boom" not in text


def _stored_preview(rows: int = 2) -> uuid.UUID:
    """A real preview in the store, so the confirm step finds it."""
    result = asyncio.run(
        bulk_upload_module.preview_buyers(
            [
                {"org_name": f"Co {n}", "domain": f"co{n}.com", "target_vertical": VERTICAL}
                for n in range(rows)
            ]
        )
    )
    return result.preview_id


def test_confirming_starts_the_add_for_the_person_who_clicked(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    started: list[dict] = []

    def fake_commit(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        started.append({"preview_id": preview_id, "requested_by": requested_by, "on_done": on_done})
        return CommitProgress(state="running", total=2)

    monkeypatch.setattr(bulk_handler, "commit", fake_commit)
    preview_id = _stored_preview(2)

    _post_interactivity(_confirm_payload(preview_id, submitter="U_TEST"))

    assert started[0]["preview_id"] == preview_id
    assert started[0]["requested_by"] == "U_TEST"  # Slack's user, not the modal's metadata
    assert slack.posted[0]["channel"] == "C_TEST"
    assert slack.posted[0]["user"] == "U_TEST"
    assert slack.posted[0]["text"].startswith("Adding 2 buyers…")


def test_the_adding_notice_is_sent_before_the_work_starts(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    seen_when_started: list[int] = []

    def fake_commit(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        seen_when_started.append(len(slack.posted))
        return CommitProgress(state="running", total=1)

    monkeypatch.setattr(bulk_handler, "commit", fake_commit)

    _post_interactivity(_confirm_payload(_stored_preview(1)))

    # A small file can finish at once, so "Adding" must already be out.
    assert seen_when_started == [1]


def test_the_done_callback_posts_the_result_to_the_person(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    captured: list = []

    def fake_commit(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        captured.append(on_done)
        return CommitProgress(state="running", total=1)

    monkeypatch.setattr(bulk_handler, "commit", fake_commit)
    _post_interactivity(_confirm_payload(_stored_preview(1)))

    asyncio.run(
        captured[0](
            CommitProgress(
                state="done",
                total=3,
                added=2,
                failed=(
                    RowOutcome(row=4, kind="failed", reason="RuntimeError; already saved: nothing"),
                ),
            )
        )
    )

    assert slack.posted[-1]["text"].startswith("*Bulk add finished.* Added 2")
    assert "Line 4: RuntimeError" in slack.posted[-1]["text"]


def test_confirming_an_expired_upload_says_so_and_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    def never(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        raise AssertionError("nothing should start for an expired upload")

    monkeypatch.setattr(bulk_handler, "commit", never)

    _post_interactivity(_confirm_payload(uuid.uuid4()))

    assert [p["text"] for p in slack.posted] == ["*This upload expired.* Upload the file again."]


def test_an_upload_that_expires_just_before_it_starts_says_so(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    def expired(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        raise bulk_upload_module.PreviewNotFoundError(str(preview_id))

    monkeypatch.setattr(bulk_handler, "commit", expired)

    _post_interactivity(_confirm_payload(_stored_preview(1)))

    assert slack.posted[-1]["text"] == "*This upload expired.* Upload the file again."


def test_a_notice_falls_back_to_a_direct_message_when_the_channel_post_fails(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    direct: list[dict] = []

    async def not_in_channel(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise SlackApiError("not_in_channel", {"ok": False, "error": "not_in_channel"})

    async def post_message(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        direct.append(kwargs)
        return {"ok": True}

    base = "slack_sdk.web.async_client.AsyncWebClient"
    monkeypatch.setattr(f"{base}.chat_postEphemeral", not_in_channel)
    monkeypatch.setattr(f"{base}.chat_postMessage", post_message)
    monkeypatch.setattr(
        bulk_handler, "commit", lambda *a, **k: CommitProgress(state="running", total=1)
    )

    _post_interactivity(_confirm_payload(_stored_preview(1)))

    assert direct[0]["channel"] == "U_TEST"  # the person, not the channel
    assert direct[0]["text"].startswith("Adding 1 buyer…")


def test_a_notice_that_cannot_be_sent_anywhere_does_not_stop_the_add(
    monkeypatch: pytest.MonkeyPatch, slack: SimpleNamespace
) -> None:
    started: list[uuid.UUID] = []

    async def fail(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise SlackApiError("channel_not_found", {"ok": False, "error": "channel_not_found"})

    def fake_commit(preview_id, *, requested_by, on_done):  # noqa: ANN001, ANN202
        started.append(preview_id)
        return CommitProgress(state="running", total=1)

    base = "slack_sdk.web.async_client.AsyncWebClient"
    monkeypatch.setattr(f"{base}.chat_postEphemeral", fail)
    monkeypatch.setattr(f"{base}.chat_postMessage", fail)
    monkeypatch.setattr(bulk_handler, "commit", fake_commit)
    preview_id = _stored_preview(1)

    _post_interactivity(_confirm_payload(preview_id))

    assert started == [preview_id]
