"""The persistence interface for the buyers concept — implemented by
`persistence/repositories/buyers_repository.py`. This bot has no matching
pipeline, so there's no separate domain value object/mapper layer the way
`matching_engine` has — the Port's methods return the ORM row directly,
same as the concrete class they abstract.
"""

from collections.abc import Sequence
from dataclasses import dataclass
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
    target_vertical: str | None
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
    target_region: list[str]
    target_country: list[str]
    last_mandate_briefing_date: date | None
    prior_gcc_acquisition: str | None
    is_active: bool | None
    legacy_entry_id: str | None
    raw_attio: JsonObject


@dataclass(frozen=True)
class BuyerFilters:
    """Every set filter must match. List filters match when any value overlaps.
    `check_size_usd` fits when it lies within the buyer's min and max; a missing
    bound doesn't exclude the buyer."""

    target_vertical: str | None = None
    mandate_status: str | None = None
    model: str | None = None
    target_region: tuple[str, ...] = ()
    target_country: tuple[str, ...] = ()
    check_size_usd: float | None = None
    hq_country: str | None = None
    sector_focus: tuple[str, ...] = ()


class BuyerRepositoryPort(Protocol):
    async def get_by_id(self, buyer_role_id: str) -> BuyerRole | None: ...
    async def get_with_organization(self, buyer_role_id: str) -> BuyerRole | None: ...
    async def get_many_with_organization(
        self, buyer_role_ids: Sequence[str]
    ) -> list[BuyerRole]: ...
    async def get_active_by_org_and_vertical(
        self, org_attio_id: str, target_vertical: str | None
    ) -> BuyerRole | None: ...
    async def create(self, org_attio_id: str, **fields: Unpack[BuyerRoleFields]) -> BuyerRole: ...
    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[BuyerRole]: ...
    async def list_filtered(
        self, filters: BuyerFilters, limit: int, offset: int = 0
    ) -> list[BuyerRole]: ...
    async def update(
        self, buyer_role_id: str, **fields: Unpack[BuyerRoleFields]
    ) -> BuyerRole | None: ...
