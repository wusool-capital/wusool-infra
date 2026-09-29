import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, SellerRole
from app.modules.matching_engine.domain.matching.narrowing import CandidateNarrowing
from app.modules.matching_engine.persistence.repositories.sellers_repository import SellerRepository
from app.modules.utilities.domain.json_types import JsonObject


async def test_get_structured_fields_returns_role_row(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    repo = SellerRepository(db_session)
    fields = await repo.get_structured_fields(str(any_seller_role.id))
    assert fields is not None
    assert fields.seller_role_id == str(any_seller_role.id)


async def test_get_eligible_sellers_excludes_inactive_and_removed(
    db_session: AsyncSession,
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Eligible Sellers Test Org")
    removed_org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Removed Org",
        removed_at=datetime.now(UTC),
    )
    db_session.add_all([org, removed_org])
    await db_session.flush()

    eligible = SellerRole(org_attio_id=org.attio_id, is_active=True)
    inactive = SellerRole(org_attio_id=org.attio_id, is_active=False)
    removed_role = SellerRole(
        org_attio_id=org.attio_id, is_active=True, removed_at=datetime.now(UTC)
    )
    role_on_removed_org = SellerRole(org_attio_id=removed_org.attio_id, is_active=True)
    db_session.add_all([eligible, inactive, removed_role, role_on_removed_org])
    await db_session.flush()

    repo = SellerRepository(db_session)
    results = await repo.get_eligible_sellers(CandidateNarrowing())
    result_ids = {r.seller_role_id for r in results}

    assert str(eligible.id) in result_ids
    assert str(inactive.id) not in result_ids
    assert str(removed_role.id) not in result_ids
    assert str(role_on_removed_org.id) not in result_ids


def _usd(amount: float) -> JsonObject:
    return {"amount": amount, "currency": "USD"}


async def _add_seller(
    db_session: AsyncSession,
    *,
    sector: list[str] | None = None,
    sector_focus: list[str] | None = None,
    region: str | None = None,
    hq_country: str | None = None,
    geographic_focus: list[str] | None = None,
    valuation_low: JsonObject | None = None,
    valuation_mid: JsonObject | None = None,
    valuation_high: JsonObject | None = None,
) -> str:
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Narrowing Test Org",
        sector_focus=sector_focus or [],
        geographic_focus=geographic_focus or [],
        region=region,
        hq_country=hq_country,
    )
    db_session.add(org)
    await db_session.flush()
    role = SellerRole(
        org_attio_id=org.attio_id,
        is_active=True,
        sector=sector or [],
        valuation_low=valuation_low,
        valuation_mid=valuation_mid,
        valuation_high=valuation_high,
    )
    db_session.add(role)
    await db_session.flush()
    return str(role.id)


async def _eligible_ids(db_session: AsyncSession, narrowing: CandidateNarrowing) -> set[str]:
    results = await SellerRepository(db_session).get_eligible_sellers(narrowing)
    return {r.seller_role_id for r in results}


async def test_vertical_narrowing_matches_either_sector_field_and_passes_missing_data(
    db_session: AsyncSession,
) -> None:
    by_role_sector = await _add_seller(db_session, sector=["Pharma Tech"])
    by_org_focus = await _add_seller(db_session, sector_focus=["pharma tech"])
    other_vertical = await _add_seller(db_session, sector=["Industrials"], sector_focus=["AI"])
    no_data = await _add_seller(db_session)

    ids = await _eligible_ids(db_session, CandidateNarrowing(vertical="pharma tech"))

    assert {by_role_sector, by_org_focus, no_data} <= ids
    assert other_vertical not in ids


async def test_geography_narrowing_uses_region_hq_country_and_focus(
    db_session: AsyncSession,
) -> None:
    gulf_narrowing = CandidateNarrowing(
        regions=frozenset({"gcc"}),
        countries=frozenset({"united arab emirates", "uae", "saudi arabia"}),
    )
    multi_country_hq = await _add_seller(
        db_session, hq_country="United Kingdom, United Arab Emirates"
    )
    region_only = await _add_seller(db_session, region="GCC")
    by_focus = await _add_seller(db_session, geographic_focus=["Saudi Arabia"])
    no_data = await _add_seller(db_session)
    abbreviated = await _add_seller(db_session, hq_country="UAE")
    wrong_hq = await _add_seller(db_session, hq_country="Pakistan")
    wrong_region = await _add_seller(db_session, region="Europe")

    ids = await _eligible_ids(db_session, gulf_narrowing)

    assert {multi_country_hq, region_only, by_focus, no_data, abbreviated} <= ids
    assert wrong_hq not in ids
    assert wrong_region not in ids


async def test_check_size_never_drops_a_seller_but_malformed_valuation_is_safe(
    db_session: AsyncSession,
) -> None:
    too_big = await _add_seller(
        db_session, valuation_low=_usd(50_000_000), valuation_high=_usd(80_000_000)
    )
    malformed = await _add_seller(db_session, valuation_low={"amount": "n/a", "currency": "USD"})

    ids = await _eligible_ids(db_session, CandidateNarrowing(ev_ceiling=1e12))

    assert {too_big, malformed} <= ids


async def test_ev_ceiling_drops_sellers_valued_above_it(db_session: AsyncSession) -> None:
    within = await _add_seller(db_session, valuation_low=_usd(10_000_000))
    above = await _add_seller(db_session, valuation_low=_usd(100_000_000))

    ids = await _eligible_ids(db_session, CandidateNarrowing(ev_ceiling=20_000_000.0))

    assert within in ids
    assert above not in ids
