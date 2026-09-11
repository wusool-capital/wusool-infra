"""Unit coverage for `DdlCommandsSellerDraftAdapter` — where `discovery`'s
hand-off actually opens a Slack modal. No real Attio/DB/Slack calls; every
collaborator is faked.
"""

import pytest

from app.models import Organization
from app.modules.ddl_commands.providers.discovery import seller_draft_adapter as module
from app.modules.discovery import SellerDraft


class _FakeSlackClient:
    def __init__(self) -> None:
        self.opened: list[dict] = []

    async def views_open(self, *, trigger_id: str, view) -> dict:
        self.opened.append({"trigger_id": trigger_id, "view": view})
        return {"ok": True}


def test_normalize_drops_select_value_not_in_vocabulary() -> None:
    normalized = module._normalize({"funding_stage": "Angel round"})  # not a real option title

    assert normalized == {}


def test_normalize_keeps_valid_select_value() -> None:
    normalized = module._normalize({"funding_stage": "Seed"})

    assert normalized == {"funding_stage": "Seed"}


def test_normalize_filters_multi_select_text_to_valid_subset() -> None:
    normalized = module._normalize({"sector_focus": ["Retail / E-Commerce", "Not A Real Sector"]})

    assert normalized == {"sector_focus": ["Retail / E-Commerce"]}


def test_normalize_drops_multi_select_text_with_no_valid_values() -> None:
    normalized = module._normalize({"sector_focus": ["Not A Real Sector"]})

    assert normalized == {}


def test_normalize_drops_none_values() -> None:
    normalized = module._normalize({"est_revenue": None})

    assert normalized == {}


async def test_open_confirm_form_with_no_existing_org_opens_prefilled_add_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeSlackClient()
    monkeypatch.setattr(module, "get_slack_client", lambda token: client)

    async def _no_candidates(term: str) -> list[Organization]:
        return []

    monkeypatch.setattr(module, "search_organizations", _no_candidates)

    draft = SellerDraft(
        org_name="Acme Co", values={"sector_focus": ["Retail / E-Commerce"]}, source_urls=()
    )

    await module.DdlCommandsSellerDraftAdapter().open_confirm_form(
        trigger_id="trigger.1", draft=draft, channel_id="C1", requested_by="U1"
    )

    assert len(client.opened) == 1
    view = client.opened[0]["view"]
    assert view.callback_id == "seller_add_form_modal"


async def test_open_confirm_form_with_existing_candidates_opens_selection_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeSlackClient()
    monkeypatch.setattr(module, "get_slack_client", lambda token: client)

    existing_org = Organization(attio_id="org-1", name="Acme Co")

    async def _one_candidate(term: str) -> list[Organization]:
        return [existing_org]

    monkeypatch.setattr(module, "search_organizations", _one_candidate)

    draft = SellerDraft(org_name="Acme Co", values={}, source_urls=())

    await module.DdlCommandsSellerDraftAdapter().open_confirm_form(
        trigger_id="trigger.1", draft=draft, channel_id="C1", requested_by="U1"
    )

    assert len(client.opened) == 1
    view = client.opened[0]["view"]
    assert view.callback_id == "organization_selection_modal"
