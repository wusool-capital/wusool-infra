"""A Deal's touches: those of its buyer and its seller, taken together."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.modules.interactions.domain.model import Touch


@dataclass(frozen=True)
class DealParties:
    """The records a Deal links to. The buyer is a Person or an Organization, never both."""

    deal_id: str
    buyer_person_id: str | None
    buyer_organization_id: str | None
    seller_organization_id: str | None


def merge_touches(groups: Iterable[Sequence[Touch]]) -> tuple[Touch, ...]:
    """One list from several, with a touch counted once however many groups hold it."""
    unique: dict[tuple[str, str, str], Touch] = {}
    for group in groups:
        for touch in group:
            unique.setdefault((touch.dedupe_key, touch.team_member, touch.contact), touch)
    return tuple(unique.values())


def deal_touches(
    deals: Iterable[DealParties],
    by_organization: Mapping[str, tuple[Touch, ...]],
    by_person: Mapping[str, tuple[Touch, ...]],
) -> dict[str, tuple[Touch, ...]]:
    """Touches per Deal id. A Deal none of whose parties has a touch is left out."""
    out: dict[str, tuple[Touch, ...]] = {}
    for deal in deals:
        merged = merge_touches(
            (
                by_person.get(deal.buyer_person_id or "", ()),
                by_organization.get(deal.buyer_organization_id or "", ()),
                by_organization.get(deal.seller_organization_id or "", ()),
            )
        )
        if merged:
            out[deal.deal_id] = merged
    return out
