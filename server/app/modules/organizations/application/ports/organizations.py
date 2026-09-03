"""Port for Organization persistence. Returns the shared ORM `Organization`
model directly, not a domain entity — mirrors `ddl_commands`' own
established convention (no matching pipeline, so no value-object/mapper
layer is warranted): every consumer today (Slack org-selection/search
modals) immediately reads ORM attributes and eager-loaded
`seller_roles`/`buyer_roles`, not business logic that needs a
framework-free representation.
"""

from datetime import date, datetime
from typing import Protocol, TypedDict, Unpack

from app.models import Organization
from app.modules.attio.providers.attio.money import MoneyJson
from app.modules.utilities.domain.json_types import JsonObject


class OrganizationFields(TypedDict, total=False):
    """Every `organizations` column `create`/`update` can set — excludes
    `attio_id`/`name` (always positional args) and `created_at`/`updated_at`
    (server-managed defaults, never caller-set)."""

    description: str | None
    type: list[str]
    client_type: str | None
    sector_focus: list[str]
    stage_focus: list[str]
    geographic_focus: list[str]
    hq_country: str | None
    domains: list[str]
    categories: list[str]
    relationship_status: str | None
    connection_strength: str | None
    owner_attio_id: str | None
    last_interaction_at: datetime | None
    estimated_arr: str | None
    funding_raised: MoneyJson | None
    removed_at: datetime | None
    angellist: str | None
    facebook: str | None
    instagram: str | None
    twitter: str | None
    twitter_follower_count: int | None
    foundation_date: date | None
    ticket_size: str | None
    lead_source: str | None
    employee_range: str | None
    linkedin: str | None
    logo_url: str | None
    is_active: bool | None
    raw_attio: JsonObject


class OrganizationRepositoryPort(Protocol):
    async def get_by_id(self, attio_id: str) -> Organization | None: ...
    async def get_by_id_with_roles(self, attio_id: str) -> Organization | None: ...
    async def search_by_name(self, term: str, limit: int = 10) -> list[Organization]: ...
    async def create(
        self, attio_id: str, name: str, **fields: Unpack[OrganizationFields]
    ) -> Organization: ...
    async def update(
        self, attio_id: str, **fields: Unpack[OrganizationFields]
    ) -> Organization | None: ...
