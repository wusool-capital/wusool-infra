from unittest.mock import AsyncMock

import pytest

from app.modules.attio.providers.attio.client import AttioError
from app.modules.matching_engine.application.errors import DealGatewayError
from app.modules.matching_engine.domain.matching.deals import QualifiedDealDraft
from app.modules.matching_engine.providers.attio.deal_gateway import AttioDealGateway


def _record(record_id: str, seller: str, stage: str = "Inbound") -> dict:
    return {
        "id": {"record_id": record_id},
        "web_url": f"https://attio/{record_id}",
        "values": {
            "deal_name": [{"value": f"Deal {record_id}"}],
            "deal_stage": [{"status": {"title": stage}}],
            "buyer_id": [{"target_record_id": "buyer-1"}],
            "seller_id": [{"target_record_id": seller}],
            "is_test": [{"value": True}],
        },
    }


class _Client:
    def __init__(self, records=()):
        self.post = AsyncMock(side_effect=self._post)
        self.patch = AsyncMock(return_value={})
        self._records = list(records)

    async def _post(self, path, body):
        if path.endswith("/query"):
            return {"data": self._records}
        return {"data": {"id": {"record_id": "new-1"}, "web_url": "https://attio/new-1"}}


def _gateway(client) -> AttioDealGateway:
    return AttioDealGateway(client, is_test=True, owner_id="owner-1")


@pytest.mark.asyncio
async def test_find_pair_deals_filters_by_seller() -> None:
    client = _Client([_record("d1", "seller-1"), _record("d2", "other")])

    found = await _gateway(client).find_pair_deals(
        buyer_attio_id="buyer-1", seller_attio_id="seller-1"
    )

    assert [d.attio_id for d in found] == ["d1"]
    assert found[0].stage == "Inbound"


@pytest.mark.asyncio
async def test_create_qualified_payload() -> None:
    client = _Client()

    deal = await _gateway(client).create_qualified(
        QualifiedDealDraft(name="S - B", buyer_attio_id="buyer-1", seller_attio_id="seller-1")
    )

    values = client.post.await_args.args[1]["data"]["values"]
    assert deal.attio_id == "new-1"
    assert values["deal_stage"] == "Qualified"
    assert values["deal_type"] == "Buy-side"
    assert values["is_test"] is True
    assert values["buyer_id"][0]["target_record_id"] == "buyer-1"
    assert values["seller_id"][0]["target_record_id"] == "seller-1"
    assert values["deal_owner"][0]["referenced_actor_id"] == "owner-1"


@pytest.mark.asyncio
async def test_promote_patches_stage() -> None:
    client = _Client()

    await _gateway(client).promote_to_qualified("d1")

    path, body = client.patch.await_args.args
    assert path.endswith("/records/d1")
    assert body == {"data": {"values": {"deal_stage": "Qualified"}}}


@pytest.mark.asyncio
async def test_attio_errors_become_gateway_errors() -> None:
    client = _Client()
    client.post = AsyncMock(side_effect=AttioError(500, "boom"))

    with pytest.raises(DealGatewayError):
        await _gateway(client).create_qualified(
            QualifiedDealDraft(name="n", buyer_attio_id="b", seller_attio_id="s")
        )
