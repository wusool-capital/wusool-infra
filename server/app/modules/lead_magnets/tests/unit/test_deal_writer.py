"""`AttioDealWriter.write`'s one-deal-per-organisation rule.

Fakes only at the network seam (`AttioClientProtocol`) — `entries.py`'s real
`find_deals_by_party`/`create_deal` run against it, same convention as
`test_person_writer.py`. The fake never pre-filters by party: it returns
whatever page of raw `deal` records was asked for, exactly like the real
Attio API would, so these tests exercise `find_deals_by_party`'s actual
client-side `v.ref` matching rather than a hand-rolled substitute for it —
see `entries.py::find_deals_by_party`'s docstring for why matching happens
client-side at all.
"""

import pytest

from app.modules.attio.providers.attio.client import AttioError
from app.modules.attio.providers.attio.write_values import ActorReferenceValue
from app.modules.lead_magnets.providers.attio.deal_writer import AttioDealWriter
from app.modules.lead_magnets.tests.attio_fixtures import RefValueEntry, ValueEntry

_RAMZY = "owner-ramzy"
_JULES = "owner-jules"
_PAGE_SIZE = 500  # must match entries.py's own `_PAGE_SIZE`


def _writer(client, *, is_test: bool = False) -> AttioDealWriter:
    return AttioDealWriter(client, is_test=is_test, owner_id=_RAMZY, fallback_owner_id=_JULES)


def _owner(owner_id: str) -> list[dict]:
    return ActorReferenceValue(
        referenced_actor_type="workspace-member", referenced_actor_id=owner_id
    ).as_value()


def _deal_record(
    record_id: str,
    *,
    seller_id: str | None = None,
    buyer_id: str | None = None,
    is_test: bool = False,
) -> dict:
    values: dict = {"is_test": ValueEntry(value=is_test).as_entries()}
    if seller_id is not None:
        values["seller_id"] = RefValueEntry(target_record_id=seller_id).as_entries()
    if buyer_id is not None:
        values["buyer_id"] = RefValueEntry(target_record_id=buyer_id).as_entries()
    return {"id": {"record_id": record_id}, "values": values}


class _FakeClient:
    def __init__(
        self,
        *,
        records: list[dict] | None = None,
        created_id: str = "deal-new",
        reject_owner: str | None = None,
    ) -> None:
        self._records = records or []
        self._created_id = created_id
        self._reject_owner = reject_owner
        self.queries: list[dict] = []
        self.create_calls: list[dict] = []

    async def post(self, path: str, json_body: dict) -> dict:
        if path == "/objects/deal/records/query":
            self.queries.append(json_body)
            offset = json_body["offset"]
            limit = json_body["limit"]
            return {"data": self._records[offset : offset + limit]}
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

    result = await _writer(client).write(org_attio_id=None, org_name="Acme", deal_type="Sell-side")

    assert result is None
    assert client.queries == []
    assert client.create_calls == []


async def test_no_match_creates_an_inbound_sell_side_deal() -> None:
    client = _FakeClient(records=[])

    result = await _writer(client).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

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
    client = _FakeClient(records=[], created_id="deal-buy")

    result = await _writer(client, is_test=True).write(
        org_attio_id="org-9", org_name="Fund", deal_type="Buy-side"
    )

    assert result == "deal-buy"
    values = client.create_calls[0]
    assert values["deal_type"] == "Buy-side"
    assert values["buyer_id"] == [{"target_object": "organizations", "target_record_id": "org-9"}]
    assert "seller_id" not in values
    assert values["is_test"] is True


async def test_existing_deal_is_reused_untouched() -> None:
    """A second tool from the same company must not add a second card, and
    must not drag a deal a human has already advanced back to `Inbound`. A
    decoy deal on a different organisation proves the match is real, not
    just "whatever the fake returned"."""
    client = _FakeClient(
        records=[
            _deal_record("deal-old", seller_id="org-1"),
            _deal_record("deal-decoy", seller_id="org-other"),
            _deal_record("deal-newer", seller_id="org-1"),
        ]
    )

    result = await _writer(client).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

    assert result == "deal-old"
    assert client.create_calls == []


async def test_the_other_half_of_the_workspace_is_ignored() -> None:
    client = _FakeClient(records=[_deal_record("deal-prod", seller_id="org-1", is_test=False)])

    result = await _writer(client, is_test=True).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

    assert result == "deal-new"
    assert client.create_calls[0]["is_test"] is True


async def test_paginates_across_more_than_one_page_of_deals() -> None:
    """A match sitting on page 2 must still be found — the whole reason
    `find_deals_by_party` pages every `deal` rather than trusting a single
    filtered request (see its docstring)."""
    filler = [_deal_record(f"filler-{i}", seller_id="org-other") for i in range(_PAGE_SIZE)]
    target = _deal_record("deal-on-page-2", seller_id="org-1")
    client = _FakeClient(records=[*filler, target])

    result = await _writer(client).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

    assert result == "deal-on-page-2"
    assert len(client.queries) == 2
    assert client.create_calls == []


async def test_a_rejected_primary_owner_retries_once_with_the_fallback() -> None:
    """The primary advisor leaving the workspace would otherwise silently
    stop every lead-magnet deal from being created."""
    client = _FakeClient(records=[], reject_owner=_RAMZY)

    result = await _writer(client).write(
        org_attio_id="org-1", org_name="Acme", deal_type="Sell-side"
    )

    assert result == "deal-new"
    assert [call["deal_owner"] for call in client.create_calls] == [_owner(_RAMZY), _owner(_JULES)]


async def test_a_rejected_fallback_owner_is_not_retried_forever() -> None:
    client = _FakeClient(records=[], reject_owner=_RAMZY)
    writer = AttioDealWriter(client, is_test=False, owner_id=_RAMZY, fallback_owner_id=_RAMZY)

    with pytest.raises(AttioError):
        await writer.write(org_attio_id="org-1", org_name="Acme", deal_type="Sell-side")

    assert len(client.create_calls) == 1
