"""Role-selection modal submission -> dispatch, without an actual Slack
workspace. Signs the request the way Slack really does, same as
`test_slack_command_dispatch.py`. Covers the one gap this module's
`@app.view` handler had relative to its sibling modules
(`matching_engine`'s `buyer_selection_modal`, `ddl_commands`' edit/add
forms): Slack redelivers view submissions, and without a guard a duplicate
delivery would spawn two background research runs (real Bedrock/Firecrawl/
Diffbot/PDL cost) and post two duplicate proposal messages.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.modules.enrichment.api.slack.handlers import actions as actions_module
from app.modules.enrichment.bootstrap import create_app
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.domain.targets import ResolvedOrgRole

app = create_app()


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _role_selection_payload(view_id: str) -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": view_id,
            "callback_id": "enrichment_role_selection_modal",
            "private_metadata": json.dumps({"channel_id": "C_TEST", "search_term": "Blue Horizon"}),
            "state": {
                "values": {
                    "role_id": {
                        "selected_role": {
                            "selected_option": {
                                "value": "seller:fae6496c-63bf-42d1-873b-e432ad2bcd39"
                            }
                        }
                    }
                }
            },
        },
    }


def _post_interactivity(payload: dict, settings) -> None:
    body = urlencode({"payload": json.dumps(payload)})
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)
    client = TestClient(app)
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )


def test_duplicate_role_selection_submission_only_proposes_once(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return [
            ResolvedOrgRole(
                org_attio_id="org-1",
                org_name="Blue Horizon",
                role_id="fae6496c-63bf-42d1-873b-e432ad2bcd39",
                kind="seller",
            )
        ]

    def fake_run(coro_factory, *, name: str) -> None:
        calls.append(name)
        coro_factory().close()  # never actually awaited — avoid a real research call

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    monkeypatch.setattr(
        "app.modules.enrichment.api.dependencies.resolve_org_roles", fake_resolve_org_roles
    )
    monkeypatch.setattr(actions_module._task_runner, "run", fake_run)

    settings = get_settings()
    payload = _role_selection_payload(view_id="V_SAME")

    first = _post_interactivity(payload, settings)
    second = _post_interactivity(payload, settings)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == ["enrich:fae6496c-63bf-42d1-873b-e432ad2bcd39"]
