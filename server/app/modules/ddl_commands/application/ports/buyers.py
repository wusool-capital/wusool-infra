"""The persistence interface for the buyers concept — implemented by
`persistence/repositories/buyers_repository.py`. This bot has no matching
pipeline, so there's no separate domain value object/mapper layer the way
`matching_engine` has — the Port's methods return the ORM row directly,
same as the concrete class they abstract.
"""

from datetime import date
from typing import Protocol, TypedDict, Unpack

from app.models import BuyerRole
from app.modules.attio.providers.attio.money import MoneyJson
from app.modules.utilities.domain.json_types import JsonObject


class BuyerRoleFields(TypedDict, total=False):
    """Every `buyer_roles` column `create`/`update` can set — excludes
    `id`/`org_attio_id` (always positional args) and `created_at`/
    `updated_at` (server-managed, never caller-set)."""

    model: str | None
    mandate_status: str | None
    ebitda_floor: MoneyJson | None
    check_size_min: MoneyJson | None
    check_size_max: MoneyJson | None
    ev_ceiling: MoneyJson | None
    deal_structure_tolerance: str | None
    earnout_tolerance: bool | None
    profitable_only: bool | None
    investment_strategy: str | None
    notes: str | None
    key_contact_attio_id: str | None
    acquisition_enrichment: str | None
    deals_introduced: int | None
    deals_converted: int | None
    ebitda_ceiling: MoneyJson | None
    estimated_aum: MoneyJson | None
    notable_investments: str | None
    key_personnel: str | None
    relationship_warmth: str | None
    target_geography: list[str]
    last_mandate_briefing_date: date | None
    prior_gcc_acquisition: str | None
    is_active: bool | None
    legacy_entry_id: str | None
    raw_attio: JsonObject


class BuyerRepositoryPort(Protocol):
    async def get_by_id(self, buyer_role_id: str) -> BuyerRole | None: ...
    async def get_with_organization(self, buyer_role_id: str) -> BuyerRole | None: ...
    async def get_by_org_attio_id(self, org_attio_id: str) -> BuyerRole | None: ...
    async def create(self, org_attio_id: str, **fields: Unpack[BuyerRoleFields]) -> BuyerRole: ...
    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[BuyerRole]: ...
    async def update(
        self, buyer_role_id: str, **fields: Unpack[BuyerRoleFields]
    ) -> BuyerRole | None: ...
