"""`list_filtered` on both role repositories, against a real Postgres."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.application.ports.buyers import BuyerFilters
from app.modules.ddl_commands.application.ports.sellers import SellerFilters
from app.modules.ddl_commands.persistence.repositories.buyers_repository import BuyerRepository
from app.modules.ddl_commands.persistence.repositories.sellers_repository import (
    SellerRepository,
)

# A vertical no real row uses, so each test sees only its own rows.
_VERTICAL = f"Test vertical {uuid.uuid4()}"


def _usd(amount: float | str) -> dict[str, float | str]:
    return {"amount": amount, "currency": "USD"}


async def _buyer(session: AsyncSession, org: Organization, **fields) -> BuyerRole:
    role = BuyerRole(org_attio_id=org.attio_id, target_vertical=_VERTICAL, is_active=True)
    for name, value in fields.items():
        setattr(role, name, value)
    session.add(role)
    await session.flush()
    return role


async def test_check_size_fits_and_unknown_bounds_still_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    fits = await _buyer(
        db_session, throwaway_org, check_size_min=_usd(1e6), check_size_max=_usd(1e7)
    )
    no_bounds = await _buyer(db_session, throwaway_org)
    malformed = await _buyer(db_session, throwaway_org, check_size_min=_usd("lots"))
    await _buyer(db_session, throwaway_org, check_size_max=_usd(2e6))  # too small
    await _buyer(db_session, throwaway_org, check_size_min=_usd(2e7))  # too big

    found = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL, check_size_usd=5e6), limit=50
    )

    assert {r.id for r in found} == {fits.id, no_bounds.id, malformed.id}


async def test_regions_overlap_and_inactive_or_removed_are_left_out(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    uae = await _buyer(db_session, throwaway_org, target_country=["United Arab Emirates", "Oman"])
    await _buyer(db_session, throwaway_org, target_country=["Egypt"])
    await _buyer(
        db_session, throwaway_org, target_country=["United Arab Emirates"], is_active=False
    )
    removed = Organization(
        attio_id=f"test-org-{uuid.uuid4()}", name="Removed", removed_at=datetime.now(UTC)
    )
    db_session.add(removed)
    await db_session.flush()
    await _buyer(db_session, removed, target_country=["United Arab Emirates"])

    found = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL, target_country=("United Arab Emirates",)),
        limit=50,
    )

    assert [r.id for r in found] == [uae.id]


async def test_limit_and_stable_order(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    roles = [await _buyer(db_session, throwaway_org) for _ in range(3)]

    found = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL), limit=2
    )

    assert [r.id for r in found] == sorted(r.id for r in roles)[:2]


async def test_sellers_filter_on_sector_and_tier(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    sector = f"Test sector {uuid.uuid4()}"
    throwaway_org.sector_focus = [sector, "Fintech"]
    match = SellerRole(org_attio_id=throwaway_org.attio_id, is_active=True, outreach_tier="Tier 1")
    other = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Other", sector_focus=[sector])
    db_session.add_all([match, other])
    await db_session.flush()
    db_session.add(SellerRole(org_attio_id=other.attio_id, is_active=True, outreach_tier="Tier 3"))
    await db_session.flush()

    found = await SellerRepository(db_session).list_filtered(
        SellerFilters(sector=sector, outreach_tier="Tier 1"), limit=50
    )

    assert [r.id for r in found] == [match.id]


async def test_hq_country_and_region_match_one_item_of_a_joined_value(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.hq_country = "United Arab Emirates, Saudi Arabia"
    throwaway_org.region = "GCC,MENA"
    role = await _buyer(db_session, throwaway_org)
    seller = SellerRole(org_attio_id=throwaway_org.attio_id, is_active=True, outreach_tier="Tier 2")
    db_session.add(seller)
    await db_session.flush()

    buyers = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL, hq_country="Saudi Arabia"), limit=50
    )
    sellers = await SellerRepository(db_session).list_filtered(
        SellerFilters(region="MENA", hq_country="United Arab Emirates", outreach_tier="Tier 2"),
        limit=50,
    )
    none = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL, hq_country="Saudi"), limit=50
    )

    assert [r.id for r in buyers] == [role.id]
    assert seller.id in {r.id for r in sellers}
    assert none == []


async def test_a_role_removed_in_attio_is_left_out(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    live = await _buyer(db_session, throwaway_org)
    await _buyer(db_session, throwaway_org, removed_at=datetime.now(UTC))

    found = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(target_vertical=_VERTICAL), limit=50
    )

    assert [r.id for r in found] == [live.id]


async def test_offset_pages_do_not_overlap_and_cover_every_row(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    roles = [await _buyer(db_session, throwaway_org) for _ in range(5)]
    repo = BuyerRepository(db_session)
    filters = BuyerFilters(target_vertical=_VERTICAL)

    pages = [await repo.list_filtered(filters, limit=2, offset=o) for o in (0, 2, 4)]

    ids = [r.id for page in pages for r in page]
    assert ids == sorted(r.id for r in roles)
    assert [len(p) for p in pages] == [2, 2, 1]


async def test_sector_focus_matches_a_buyer_whose_vertical_differs(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    sector = f"Test sector {uuid.uuid4()}"
    throwaway_org.sector_focus = [sector, "Fintech"]
    in_focus = await _buyer(db_session, throwaway_org)  # target_vertical is _VERTICAL
    other = Organization(
        attio_id=f"test-org-{uuid.uuid4()}", name="Other", sector_focus=["Fintech"]
    )
    db_session.add(other)
    await db_session.flush()
    await _buyer(db_session, other)

    found = await BuyerRepository(db_session).list_filtered(
        BuyerFilters(sector_focus=(sector, "No such sector")), limit=50
    )

    assert [r.id for r in found] == [in_focus.id]


async def test_get_many_with_organization_skips_unknown_ids(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    buyer = await _buyer(db_session, throwaway_org)
    seller = SellerRole(org_attio_id=throwaway_org.attio_id, is_active=True)
    db_session.add(seller)
    await db_session.flush()

    buyers = await BuyerRepository(db_session).get_many_with_organization(
        [str(buyer.id), str(uuid.uuid4()), str(seller.id)]
    )
    sellers = await SellerRepository(db_session).get_many_with_organization(
        [str(seller.id), str(buyer.id)]
    )

    assert [r.id for r in buyers] == [buyer.id]
    assert [r.id for r in sellers] == [seller.id]
    assert buyers[0].organization.attio_id == throwaway_org.attio_id
