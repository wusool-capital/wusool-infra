"""Unit coverage for `DdlCommandsReviewAdapter` — the hand-off enrichment
reaches through `EnrichmentReviewPort` to open a real, prefilled
`/edit-seller`/`/edit-buyer` modal. No real Attio/DB/Slack calls.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.modules.ddl_commands.providers.enrichment import review_adapter as module
from app.modules.enrichment import (
    EnrichmentTarget,
    EnrichmentTargetKind,
    ProposedFieldValue,
    WriteTarget,
)


class _FakeSlackClient:
    def __init__(self) -> None:
        self.opened: list[dict] = []

    async def views_open(self, *, trigger_id: str, view) -> dict:
        self.opened.append({"trigger_id": trigger_id, "view": view})
        return {"ok": True}


def _fake_org(attio_id: str = "org-1", name: str = "Acme Co") -> SimpleNamespace:
    return SimpleNamespace(attio_id=attio_id, name=name, hq_country=None, employee_range=None)


def _fake_seller_role(role_id: uuid.UUID, org) -> SimpleNamespace:
    return SimpleNamespace(id=role_id, organization=org, est_revenue=None, years_active=None)


def _fake_buyer_role(role_id: uuid.UUID, org) -> SimpleNamespace:
    return SimpleNamespace(id=role_id, organization=org, investment_strategy=None)


@pytest.fixture
def slack_client(monkeypatch: pytest.MonkeyPatch) -> _FakeSlackClient:
    client = _FakeSlackClient()
    monkeypatch.setattr(module, "get_slack_client", lambda token: client)
    return client


def _target(kind: EnrichmentTargetKind, role_id: uuid.UUID) -> EnrichmentTarget:
    return EnrichmentTarget(kind=kind, role_id=role_id, org_attio_id="org-1", org_name="Acme Co")


async def test_open_review_form_with_no_values_does_nothing(
    slack_client: _FakeSlackClient,
) -> None:
    await module.DdlCommandsReviewAdapter().open_review_form(
        trigger_id="trigger.1",
        target=_target(EnrichmentTargetKind.SELLER, uuid.uuid4()),
        values=(),
        channel_id="C1",
        requested_by="U1",
    )

    assert slack_client.opened == []


async def test_open_review_form_opens_prefilled_seller_edit_form(
    monkeypatch: pytest.MonkeyPatch, slack_client: _FakeSlackClient
) -> None:
    role_id = uuid.uuid4()
    org = _fake_org()
    role = _fake_seller_role(role_id, org)
    monkeypatch.setattr(module, "resolve_seller_by_id", _async_returning(role))

    values = (
        ProposedFieldValue(
            field_name="est_revenue",
            write_target=WriteTarget.SELLER_ROLE,
            current=None,
            proposed=5_000_000.0,
            source_url="https://example.com",
            confidence=0.9,
            rationale="",
        ),
        ProposedFieldValue(
            field_name="hq_country",
            write_target=WriteTarget.ORGANIZATION,
            current=None,
            proposed="United Arab Emirates",
            source_url="https://example.com",
            confidence=0.9,
            rationale="",
        ),
    )

    await module.DdlCommandsReviewAdapter().open_review_form(
        trigger_id="trigger.1",
        target=_target(EnrichmentTargetKind.SELLER, role_id),
        values=values,
        channel_id="C1",
        requested_by="U1",
    )

    assert len(slack_client.opened) == 1
    view = slack_client.opened[0]["view"]
    assert view.callback_id == "seller_edit_form_modal"
    block_ids = {b.to_dict()["block_id"] for b in view.blocks if hasattr(b, "block_id")}
    assert "est_revenue" in block_ids
    assert "org_hq_country" in block_ids


async def test_open_review_form_drops_a_select_value_not_in_the_live_vocabulary(
    monkeypatch: pytest.MonkeyPatch, slack_client: _FakeSlackClient
) -> None:
    role_id = uuid.uuid4()
    org = _fake_org()
    role = _fake_seller_role(role_id, org)
    monkeypatch.setattr(module, "resolve_seller_by_id", _async_returning(role))

    values = (
        ProposedFieldValue(
            field_name="employee_range",
            write_target=WriteTarget.ORGANIZATION,
            current=None,
            proposed="around fifty people",  # not a live option title
            source_url="https://example.com",
            confidence=0.9,
            rationale="",
        ),
    )

    await module.DdlCommandsReviewAdapter().open_review_form(
        trigger_id="trigger.1",
        target=_target(EnrichmentTargetKind.SELLER, role_id),
        values=values,
        channel_id="C1",
        requested_by="U1",
    )

    # Nothing survived normalization — no modal is worth opening.
    assert slack_client.opened == []


async def test_open_review_form_opens_prefilled_buyer_edit_form(
    monkeypatch: pytest.MonkeyPatch, slack_client: _FakeSlackClient
) -> None:
    role_id = uuid.uuid4()
    org = _fake_org()
    role = _fake_buyer_role(role_id, org)
    monkeypatch.setattr(module, "resolve_buyer_by_id", _async_returning(role))

    values = (
        ProposedFieldValue(
            field_name="investment_strategy",
            write_target=WriteTarget.BUYER_ROLE,
            current=None,
            proposed="Buy-and-build in GCC services",
            source_url="https://example.com",
            confidence=0.9,
            rationale="",
        ),
    )

    await module.DdlCommandsReviewAdapter().open_review_form(
        trigger_id="trigger.1",
        target=_target(EnrichmentTargetKind.BUYER, role_id),
        values=values,
        channel_id="C1",
        requested_by="U1",
    )

    assert len(slack_client.opened) == 1
    assert slack_client.opened[0]["view"].callback_id == "buyer_edit_form_modal"


def _async_returning(value):
    async def _fn(*_args, **_kwargs):
        return value

    return _fn
