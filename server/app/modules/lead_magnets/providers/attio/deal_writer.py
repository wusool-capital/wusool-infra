"""Writes a submission's Attio `deal` record, at stage `Inbound`.

Same shape as `person_writer.py` — a thin class over `entries.py`'s
low-level helpers, query-then-create — and the same reason for it: neither
`deal.seller_id` nor `deal.buyer_id` is unique, so there is no atomic
upsert to lean on.

One deal per organisation, not per submission. A company that runs the
valuation tool and then the benchmark is one inbound lead, not two, and the
second run must not drop a duplicate card into the pipeline. A matched deal
is returned untouched: its stage is a human's working state, and a later
lead magnet must never drag a `Qualified` deal back to `Inbound`.

`owner_id` is mandatory in practice even though Attio does not mark
`deal_owner` required: every deal in the live workspace has one, so an
unowned lead-magnet deal would be the only unassigned card in the pipeline.
A rejected create is retried once with `fallback_owner_id` — the primary
advisor leaving the workspace would otherwise silently stop every
lead-magnet deal from being created, visible only as a log line.

Failure here is the caller's call, not this class's: see
`bootstrap.py::_RoleAttioWriter._with_deal`.
"""

import logging

from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio import entries
from app.modules.attio.providers.attio import values as v
from app.modules.attio.providers.attio.client import AttioError
from app.modules.lead_magnets.domain.shared.attio_values import (
    DEAL_PARTY_FIELD,
    DealType,
    deal_values,
)

logger = logging.getLogger(__name__)


class AttioDealWriter:
    def __init__(
        self,
        client: AttioClientProtocol,
        *,
        is_test: bool,
        owner_id: str,
        fallback_owner_id: str,
    ) -> None:
        self._client = client
        self._is_test = is_test
        self._owner_id = owner_id
        self._fallback_owner_id = fallback_owner_id

    async def write(
        self, *, org_attio_id: str | None, org_name: str, deal_type: DealType
    ) -> tuple[str, str | None] | None:
        """Returns `(deal record id, web_url)`, or `None` when there is no
        organisation to hang it off — not an error, just nothing to link.
        """
        if not org_attio_id:
            return None

        matches = await entries.find_deals_by_party(
            self._client,
            field=DEAL_PARTY_FIELD[deal_type],
            org_attio_id=org_attio_id,
            is_test=self._is_test,
        )
        if matches:
            # Oldest wins — `find_deals_by_party` already sorts `created_at
            # asc`, so this is simply the first result.
            return v.record_id(matches[0]), v.web_url(matches[0])

        try:
            return await self._create(org_name, org_attio_id, deal_type, self._owner_id)
        except AttioError as exc:
            if self._fallback_owner_id == self._owner_id:
                raise
            logger.warning("lead_magnet_deal_owner_rejected status=%s", exc.status)
            return await self._create(org_name, org_attio_id, deal_type, self._fallback_owner_id)

    async def _create(
        self, org_name: str, org_attio_id: str, deal_type: DealType, owner_id: str
    ) -> tuple[str, str | None]:
        return await entries.create_deal(
            self._client,
            deal_values(
                name=org_name,
                org_attio_id=org_attio_id,
                deal_type=deal_type,
                owner_id=owner_id,
            ),
            is_test=self._is_test,
        )
