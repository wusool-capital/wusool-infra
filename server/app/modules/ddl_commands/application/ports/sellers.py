"""The persistence interface for the sellers concept — implemented by
`persistence/repositories/sellers_repository.py`. Same rationale as
`application.ports.buyers.BuyerRepositoryPort`: no domain layer, the Port's
methods return the ORM row directly.
"""

from datetime import date
from typing import Protocol, TypedDict, Unpack

from app.models import SellerRole
from app.modules.attio.providers.attio.money import MoneyJson
from app.modules.utilities.domain.json_types import JsonObject


class SellerRoleFields(TypedDict, total=False):
    """Every `seller_roles` column `create`/`update` can set — excludes
    `id`/`org_attio_id` (always positional args) and `created_at`/
    `updated_at` (server-managed, never caller-set)."""

    outreach_tier: str | None
    appetite_signal: str | None
    relationship_status: str | None
    est_revenue: MoneyJson | None
    est_ebitda: MoneyJson | None
    owner_salary: MoneyJson | None
    valuation_low: MoneyJson | None
    valuation_mid: MoneyJson | None
    valuation_high: MoneyJson | None
    sell_timeline: str | None
    readiness_score: float | None
    readiness_band: str | None
    last_attempt_date: date | None
    last_attempt_channel: str | None
    last_attempt_outcome: str | None
    lead_quality_score: float | None
    re_engage_date: date | None
    is_active: bool | None
    legacy_entry_id: str | None
    years_active: int | None
    funding_stage: str | None
    revenue_last_full_year: MoneyJson | None
    revenue_year_before: MoneyJson | None
    gross_margin_pct: float | None
    ebitda_deducts_salary: bool | None
    annual_rent_cost: MoneyJson | None
    largest_customer_revenue_pct: float | None
    repeat_revenue_pct: float | None
    location_count: int | None
    raw_attio: JsonObject


class SellerRepositoryPort(Protocol):
    async def get_by_id(self, seller_role_id: str) -> SellerRole | None: ...
    async def get_with_organization(self, seller_role_id: str) -> SellerRole | None: ...
    async def get_by_org_attio_id(self, org_attio_id: str) -> SellerRole | None: ...
    async def create(
        self, org_attio_id: str, **fields: Unpack[SellerRoleFields]
    ) -> SellerRole: ...
    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[SellerRole]: ...
    async def update(
        self, seller_role_id: str, **fields: Unpack[SellerRoleFields]
    ) -> SellerRole | None: ...
