"""Role-selection modal submission -> dispatch, without an actual Slack
workspace. Signs the request the way Slack really does, same as
`test_slack_command_dispatch.py`. Covers the one gap this module's
`@app.view` handler had relative to its sibling modules
(`matching_engine`'s `buyer_selection_modal`, `ddl_commands`' edit/add
forms): Slack redelivers view submissions, and without a guard a duplicate
delivery would spawn two background research runs (real Bedrock/Firecrawl/
Diffbot/PDL cost) and post two duplicate proposal messages.
"""

import json

from app.modules.enrichment.api.slack.handlers import actions as actions_module
from app.modules.enrichment.bootstrap import create_app
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.domain.targets import ResolvedOrgRole
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral
from tests.slack_test_helpers import post_interactivity as _shared_post_interactivity

app = create_app()


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


def _post_interactivity(payload: dict, settings):
    return _shared_post_interactivity(app, settings.slack_signing_secret, payload)


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

    mock_slack_auth(monkeypatch)
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


def test_stale_selection_notifies_the_operator_instead_of_silently_no_oping(
    monkeypatch,
) -> None:
    """The candidate set can change between the modal being built and
    submitted (a role deactivated, an org renamed) — the operator must see
    something went wrong, not a modal that just closes with no result.
    """
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return []  # nothing matches anymore

    def fail_if_called(coro_factory, *, name: str) -> None:
        raise AssertionError("must not propose anything for a stale selection")

    monkeypatch.setattr(
        "app.modules.enrichment.api.dependencies.resolve_org_roles", fake_resolve_org_roles
    )
    monkeypatch.setattr(actions_module._task_runner, "run", fail_if_called)

    settings = get_settings()
    payload = _role_selection_payload(view_id="V_STALE")

    response = _post_interactivity(payload, settings)

    assert response.status_code == 200
    assert len(posted) == 1
    assert "no longer available" in posted[0]["text"]
