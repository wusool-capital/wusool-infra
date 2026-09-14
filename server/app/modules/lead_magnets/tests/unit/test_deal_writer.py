"""`AttioDealWriter.write`'s one-deal-per-organisation rule.

Fakes only at the network seam (`AttioClientProtocol`) — `entries.py`'s real
`find_deals_by_party`/`create_deal` run against it, same convention as
`test_person_writer.py`.
"""

import pytest

from app.modules.attio.providers.attio.client import AttioError
from app.modules.lead_magnets.providers.attio.deal_writer import AttioDealWriter

_RAMZY = "owner-ramzy"
_JULES = "owner-jules"


def _writer(client, *, is_test: bool = False) -> AttioDealWriter:
    return AttioDealWriter(client, is_test=is_test, owner_id=_RAMZY, fallback_owner_id=_JULES)


def _owner(owner_id: str) -> list[dict]:
    return [{"referenced_actor_type": "workspace-member", "referenced_actor_id": owner_id}]


def _deal(record_id: str, *, is_test: bool = False) -> dict:
    return {
        "id": {"record_id": record_id},
        "values": {"is_test": [{"active_until": None, "value": is_test}]},
    }


class _FakeClient:
    def __init__(
        self,
        *,
        matches: list[dict] | None = None,
        created_id: str = "deal-new",
        reject_owner: str | None = None,
    ) -> None:
        self._matches = matches or []
        self._created_id = created_id
        self._reject_owner = reject_owner
        self.queries: list[dict] = []
        self.create_calls: list[dict] = []

    async def post(self, path: str, json_body: dict) -> dict:
        if path == "/objects/deal/records/query":
            self.queries.append(json_body["filter"])
            return {"data": self._matches}
        if path == "/objects/deal/records":
            values = json_body["data"]["values"]
            self.create_calls.append(values)
            if self._reject_owner is not None and values["deal_owner"] == _owner(
                self._reject_owner
            ):
                raise AttioError(400, "unknown workspace member")
            return {"data": {"id": {"record_id": self._created_id}}}
        raise AssertionError(f"unexpected post {path}")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("a matched deal must never be patched")

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")


async def test_no_organisation_skips_the_write_entirely() -> None:
    client = _FakeClient()
    writer = _writer(client, is_test=False)

    result = await writer.write(org_attio_id=None, org_name="Acme", deal_type="Sell-side")

    assert result is None
    assert client.queries == []
    assert client.create_calls == []


async def test_no_match_creates_an_inbound_sell_side_deal() -> None:
    client = _FakeClient(matches=[])
    writer = _writer(client, is_test=False)

    result = await writer.write(org_attio_id="org-1", org_name="Acme", deal_type="Sell-side")

    assert result == "deal-new"
    assert client.create_calls == [
        {
            "deal_name": "Acme",
            "deal_stage": "Inbound",
            "deal_type": "Sell-side",
            "seller_id": [{"target_object": "organizations", "target_record_id": "org-1"}],
            "deal_owner": _owner(_RAMZY),
            "is_test": False,
        }
    ]


async def test_buyer_network_writes_buy_side_against_buyer_id() -> None:
    client = _FakeClient(matches=[])
    writer = _writer(client, is_test=True)

    await writer.write(org_attio_id="org-9", org_name="Fund", deal_type="Buy-side")

    assert client.queries == [
        {"buyer_id": {"target_object": "organizations", "target_record_id": "org-9"}}
    ]
    values = client.create_calls[0]
    assert values["deal_type"] == "Buy-side"
    assert values["buyer_id"] == [{"target_object": "organizations", "target_record_id": "org-9"}]
    assert "seller_id" not in values
    assert values["is_test"] is True


async def test_existing_deal_is_reused_untouched() -> None:
    """A second tool from the same company must not add a second card, and
    must not drag a deal a human has already advanced back to `Inbound`."""
    client = _FakeClient(matches=[_deal("deal-old"), _deal("deal-newer")])
    writer = _writer(client, is_test=False)

    result = await writer.write(org_attio_id="org-1", org_name="Acme", deal_type="Sell-side")

    assert result == "deal-old"
    assert client.create_calls == []


async def test_the_other_half_of_the_workspace_is_ignored() -> None:
    client = _FakeClient(matches=[_deal("deal-prod", is_test=False)])
    writer = _writer(client, is_test=True)

    result = await writer.write(org_attio_id="org-1", org_name="Acme", deal_type="Sell-side")

    assert result == "deal-new"
    assert client.create_calls[0]["is_test"] is True


async def test_a_rejected_primary_owner_retries_once_with_the_fallback() -> None:
    """The primary advisor leaving the workspace would otherwise silently
    stop every lead-magnet deal from being created."""
    client = _FakeClient(matches=[], reject_owner=_RAMZY)

    result = await _writer(client).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

    assert result == "deal-new"
    assert [call["deal_owner"] for call in client.create_calls] == [
        _owner(_RAMZY),
        _owner(_JULES),
    ]


async def test_a_rejected_fallback_owner_is_not_retried_forever() -> None:
    client = _FakeClient(matches=[], reject_owner=None)
    client._reject_owner = _RAMZY  # both ids reject below

    writer = AttioDealWriter(client, is_test=False, owner_id=_RAMZY, fallback_owner_id=_RAMZY)
    with pytest.raises(AttioError):
        await writer.write(org_attio_id="org-1", org_name="Acme", deal_type="Sell-side")

    assert len(client.create_calls) == 1
