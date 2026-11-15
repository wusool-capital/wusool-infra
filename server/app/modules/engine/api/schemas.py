"""The Buyers and Sellers page payloads, shaped like the Engine's own universe types."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.crm import (
    ApiModel,
    BuyerFilterOptionsView,
    BuyerRoleView,
    PersonView,
    SellerFilterOptionsView,
    SellerRoleView,
    TeamMemberView,
)

# A block a later phase fills; its connector is named in `unavailable`.
Reserved = Literal["mandates", "outreach"]


class ReservedItem(ApiModel):
    """Placeholder row type. The lists below are always empty until their phase."""

    id: str


class _Universe(ApiModel):
    """`matched`, `total` and `options` come with the first page; later pages hold rows only."""

    now: datetime
    users: list[TeamMemberView]
    people: list[PersonView]
    # Deals and counterparties arrive with mandates (phase 3), emails with outreach (phase 4).
    deals: list[ReservedItem] = Field(default_factory=list, max_length=0)
    counterparties: list[ReservedItem] = Field(default_factory=list, max_length=0)
    emails: list[ReservedItem] = Field(default_factory=list, max_length=0)
    unavailable: list[Reserved]
    matched: int
    total: int
    next_cursor: str | None


class BuyersUniverseView(_Universe):
    buyers: list[BuyerRoleView]
    options: BuyerFilterOptionsView


class SellersUniverseView(_Universe):
    sellers: list[SellerRoleView]
    options: SellerFilterOptionsView
