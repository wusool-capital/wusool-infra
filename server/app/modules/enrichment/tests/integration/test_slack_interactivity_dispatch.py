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
import uuid

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


def test_buyer_organization_submission_opens_vertical_step(monkeypatch) -> None:
    from app.modules.enrichment.api.slack.views.buyer_selection import (
        BuyerSelectionMetadata,
        encode_roles,
    )

    roles = [
        ResolvedOrgRole(
            org_attio_id="org-1",
            org_name="Google Ventures",
            role_id=f"role-{vertical}",
            kind="buyer",
            target_vertical=vertical,
        )
        for vertical in ("Banking / Commercial", "Healthcare")
    ]
    mock_slack_auth(monkeypatch)

    def fail_if_called(coro_factory, *, name: str) -> None:
        raise AssertionError("must not enrich before the vertical is chosen")

    monkeypatch.setattr(actions_module._task_runner, "run", fail_if_called)

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V_BUYER_ORG",
            "callback_id": "enrichment_buyer_organization_modal",
            "private_metadata": BuyerSelectionMetadata(
                requested_by="U_TEST", channel_id="C_TEST", roles_token=encode_roles(roles)
            ).model_dump_json(),
            "state": {
                "values": {
                    "organization_id": {
                        "selected_organization": {"selected_option": {"value": "org-1"}}
                    }
                }
            },
        },
    }

    response = _post_interactivity(payload, get_settings())

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "enrichment_buyer_vertical_modal"


def test_buyer_vertical_submission_passes_guidance_to_enrichment(monkeypatch) -> None:
    from app.modules.enrichment.api.slack.views.buyer_selection import (
        BuyerSelectionMetadata,
        encode_roles,
    )

    role = ResolvedOrgRole(
        org_attio_id="org-1",
        org_name="Google Ventures",
        role_id="fae6496c-63bf-42d1-873b-e432ad2bcd39",
        kind="buyer",
        target_vertical="Healthcare",
    )
    mock_slack_auth(monkeypatch)
    captured: list[str | None] = []

    def fake_propose_and_post(target, *, channel_id: str, guidance: str | None = None):  # noqa: ANN001, ANN202
        captured.append(guidance)

        async def _noop() -> None: ...

        return _noop()

    def fake_run(coro_factory, *, name: str) -> None:
        coro_factory().close()

    monkeypatch.setattr(actions_module, "propose_and_post", fake_propose_and_post)
    monkeypatch.setattr(actions_module._task_runner, "run", fake_run)

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V_BUYER_VERTICAL",
            "callback_id": "enrichment_buyer_vertical_modal",
            "private_metadata": BuyerSelectionMetadata(
                requested_by="U_TEST", channel_id="C_TEST", roles_token=encode_roles([role])
            ).model_dump_json(),
            "state": {
                "values": {
                    "buyer_vertical": {
                        "selected_vertical": {
                            "selected_option": {"value": "fae6496c-63bf-42d1-873b-e432ad2bcd39"}
                        }
                    },
                    "guidance": {"guidance_text": {"value": "  focus on AUM  "}},
                }
            },
        },
    }

    response = _post_interactivity(payload, get_settings())

    assert response.status_code == 200
    assert captured == ["focus on AUM"]


def test_duplicate_buyer_vertical_submission_only_enriches_once(monkeypatch) -> None:
    from app.modules.enrichment.api.slack.views.buyer_selection import (
        BuyerSelectionMetadata,
        encode_roles,
    )

    role_id = "fae6496c-63bf-42d1-873b-e432ad2bcd39"
    role = ResolvedOrgRole(
        org_attio_id="org-1", org_name="Google Ventures", role_id=role_id, kind="buyer"
    )
    mock_slack_auth(monkeypatch)
    calls: list[str] = []

    def fake_run(coro_factory, *, name: str) -> None:
        calls.append(name)

    monkeypatch.setattr(actions_module._task_runner, "run", fake_run)
    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V_BUYER_DUP",
            "callback_id": "enrichment_buyer_vertical_modal",
            "private_metadata": BuyerSelectionMetadata(
                requested_by="U_TEST", channel_id="C_TEST", roles_token=encode_roles([role])
            ).model_dump_json(),
            "state": {
                "values": {
                    "buyer_vertical": {
                        "selected_vertical": {"selected_option": {"value": role_id}}
                    },
                    "guidance": {"guidance_text": {"value": None}},
                }
            },
        },
    }

    settings = get_settings()
    assert _post_interactivity(payload, settings).status_code == 200
    assert _post_interactivity(payload, settings).status_code == 200
    assert calls == [f"enrich:{role_id}"]


def test_review_click_hands_the_card_token_to_the_review_form(monkeypatch) -> None:
    from app.modules.enrichment.api.slack.views.proposal_message import _encode_proposal
    from app.modules.enrichment.domain.proposals import EnrichmentProposal
    from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind

    proposal = EnrichmentProposal(
        target=EnrichmentTarget(
            kind=EnrichmentTargetKind.BUYER,
            role_id=uuid.UUID("fae6496c-63bf-42d1-873b-e432ad2bcd39"),
            org_attio_id="org-1",
            org_name="Google Ventures",
        ),
        values=(),
        generated_by_model="m",
    )
    mock_slack_auth(monkeypatch)
    opened: list[str | None] = []

    class FakeService:
        async def open_review_form(self, *, card_token: str | None = None, **_kwargs) -> None:  # noqa: ANN003
            opened.append(card_token)

    monkeypatch.setattr(
        "app.modules.enrichment.api.dependencies.enrichment_service", lambda: FakeService()
    )
    monkeypatch.setattr(actions_module, "store_review_card", lambda body: "card-1")

    payload = {
        "type": "block_actions",
        "user": {"id": "U_TEST"},
        "trigger_id": "T1",
        "channel": {"id": "C_TEST"},
        "actions": [
            {
                "action_id": "enrichment_review",
                "block_id": "enrichment_review_block",
                "value": _encode_proposal(proposal),
            }
        ],
    }

    response = _post_interactivity(payload, get_settings())

    assert response.status_code == 200
    assert opened == ["card-1"]
