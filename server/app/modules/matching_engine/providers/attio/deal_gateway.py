"""Attio side of an approval: find, create and promote the pair's deal.

Deliberately not `lead_magnets`' `AttioDealWriter`: that writer is
one-deal-per-organisation and never moves a deal off its current stage,
so it can neither create a Qualified deal nor promote an Inbound one.
"""

import aiohttp

from app.modules.attio.domain.records import AttioRecord
from app.modules.attio.providers.attio import entries
from app.modules.attio.providers.attio import values as v
from app.modules.attio.providers.attio.client import AttioClient, AttioError
from app.modules.attio.providers.attio.write_values import (
    ActorReferenceValue,
    RecordReferenceValue,
)
from app.modules.matching_engine.application.errors import DealGatewayError
from app.modules.matching_engine.domain.matching.deals import (
    QUALIFIED_STAGE,
    ExistingDeal,
    QualifiedDealDraft,
)

_DEAL_TYPE = "Buy-side"


def _to_existing(record: AttioRecord) -> ExistingDeal:
    values = v.vals(record)
    return ExistingDeal(
        attio_id=v.record_id(record),
        name=v.first(values, "deal_name") or "Unnamed Deal",
        stage=v.first(values, "deal_stage"),
        web_url=v.web_url(record),
    )


class AttioDealGateway:
    def __init__(self, client: AttioClient, *, is_test: bool, owner_id: str) -> None:
        self._client = client
        self._is_test = is_test
        self._owner_id = owner_id

    async def find_pair_deals(
        self, *, buyer_attio_id: str, seller_attio_id: str
    ) -> list[ExistingDeal]:
        try:
            records = await entries.find_deals_by_party(
                self._client, field="buyer_id", org_attio_id=buyer_attio_id, is_test=self._is_test
            )
        except (AttioError, aiohttp.ClientError) as exc:
            raise DealGatewayError(str(exc)) from exc
        return [
            _to_existing(r) for r in records if v.ref(v.vals(r), "seller_id") == seller_attio_id
        ]

    async def create_qualified(self, draft: QualifiedDealDraft) -> ExistingDeal:
        values: dict[str, object] = {
            "deal_name": draft.name,
            "deal_stage": QUALIFIED_STAGE,
            "deal_type": _DEAL_TYPE,
            "deal_owner": ActorReferenceValue(
                referenced_actor_type="workspace-member", referenced_actor_id=self._owner_id
            ).as_value(),
            "buyer_id": RecordReferenceValue(
                target_object="organizations", target_record_id=draft.buyer_attio_id
            ).as_value(),
            "seller_id": RecordReferenceValue(
                target_object="organizations", target_record_id=draft.seller_attio_id
            ).as_value(),
        }
        try:
            record_id, web_url = await entries.create_deal(
                self._client, values, is_test=self._is_test
            )
        except (AttioError, aiohttp.ClientError) as exc:
            raise DealGatewayError(str(exc)) from exc
        return ExistingDeal(
            attio_id=record_id, name=draft.name, stage=QUALIFIED_STAGE, web_url=web_url
        )

    async def promote_to_qualified(self, deal_attio_id: str) -> None:
        try:
            await entries.patch_deal(self._client, deal_attio_id, {"deal_stage": QUALIFIED_STAGE})
        except (AttioError, aiohttp.ClientError) as exc:
            raise DealGatewayError(str(exc)) from exc
