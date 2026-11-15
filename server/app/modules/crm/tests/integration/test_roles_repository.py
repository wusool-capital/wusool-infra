"""The Postgres reads against a real database: filters, search, cursor paging, counts."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import BuyerRole, Organization, Person, SellerRole, User
from app.modules.crm.domain.roles import (
    BuyerFilters,
    InvalidCursorError,
    Range,
    SellerFilters,
)
from app.modules.crm.persistence.roles_repository import PostgresRolesRepository


def _money(amount: float) -> dict[str, object]:
    return {"amount": amount, "currency": "USD"}


@pytest.fixture
async def repo(db_session: AsyncSession) -> AsyncIterator[PostgresRolesRepository]:
    db_session.add(User(attio_id="u1", name="Jules", email="Jules@WusoolCapital.com", active=True))
    db_session.add(User(attio_id="u2", name="Gone", email="gone@wusoolcapital.com", active=False))
    await db_session.flush()
    for index, (name, domain) in enumerate(
        [("Alpha Capital", "alpha.com"), ("Beta Partners", "beta.com"), ("Gamma Fund", "gamma.com")]
    ):
        db_session.add(
            Organization(
                attio_id=f"o{index}",
                name=name,
                domains=[domain],
                hq_country="United Arab Emirates",
                region="GCC" if index < 2 else "Levant",
                owner_attio_id="u1",
            )
        )
    db_session.add(Organization(attio_id="removed", name="Zeta", removed_at=datetime.now(UTC)))
    await db_session.flush()
    db_session.add(
        Person(attio_id="p0", name="Rania Haddad", company_attio_id="o0", email=["r@alpha.com"])
    )
    db_session.add(Person(attio_id="p1", name="Omar Said", company_attio_id="o1", email=[]))
    await db_session.flush()
    db_session.add_all(
        [
            BuyerRole(
                org_attio_id="o0",
                target_vertical="Dental",
                target_region=["GCC"],
                target_country=[],
                check_size_min=_money(1e6),
                check_size_max=_money(5e6),
                ebitda_floor=_money(5e5),
                mandate_status="Active",
                key_contact_attio_id="p0",
                notes="likes clinics",
                is_active=True,
            ),
            BuyerRole(
                org_attio_id="o1",
                target_vertical="Veterinary",
                target_region=[],
                target_country=["Saudi Arabia"],
                check_size_min=_money(10e6),
                check_size_max=_money(20e6),
                is_active=True,
            ),
            BuyerRole(
                org_attio_id="o2",
                target_vertical="Dental",
                target_region=["Levant"],
                target_country=[],
                is_active=True,
            ),
            BuyerRole(org_attio_id="removed", target_vertical="Dental", is_active=True),
            BuyerRole(org_attio_id="o2", target_vertical="Logistics", is_active=False),
            SellerRole(
                org_attio_id="o0",
                sector=["Dental"],
                appetite_signal="Warm Introduction / Direct Outreach",
                est_revenue=_money(4e6),
                is_active=True,
            ),
            SellerRole(org_attio_id="o1", sector=["Retail"], appetite_signal=None, is_active=True),
            SellerRole(
                org_attio_id="o2",
                sector=["Dental", "Retail"],
                appetite_signal="Listed on Business-for-Sale Platform",
                est_revenue=_money(40e6),
                is_active=True,
            ),
        ]
    )
    await db_session.flush()
    bind = db_session.bind
    yield PostgresRolesRepository(
        async_sessionmaker(
            bind=bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
    )


async def test_only_live_buyers_are_listed_in_name_order_with_counts_and_options(
    repo: PostgresRolesRepository,
) -> None:
    page = await repo.buyers_page(BuyerFilters(), None, 100)

    assert [row.name for row in page.rows] == ["Alpha Capital", "Beta Partners", "Gamma Fund"]
    assert (page.matched, page.total, page.next_cursor) == (3, 3, None)
    assert page.options.sectors == ("Dental", "Veterinary")
    assert page.options.geographies == ("GCC", "Levant", "Saudi Arabia")
    assert page.options.statuses == ("Active",)
    assert [u.name for u in page.users] == ["Jules"]
    first = page.rows[0]
    assert (first.sectors, first.geographies, first.website) == (("Dental",), ("GCC",), "alpha.com")
    assert (first.check_size_min_usd, first.owner_id, first.contact_ids) == (1e6, "u1", ("p0",))
    assert [p.name for p in page.people] == ["Rania Haddad"]
    assert page.people[0].email == "r@alpha.com"


async def test_the_cursor_continues_without_repeating_rows(repo: PostgresRolesRepository) -> None:
    first = await repo.buyers_page(BuyerFilters(), None, 2)
    second = await repo.buyers_page(BuyerFilters(), first.next_cursor, 2)

    assert [r.name for r in first.rows] == ["Alpha Capital", "Beta Partners"]
    assert first.next_cursor is not None
    assert [r.name for r in second.rows] == ["Gamma Fund"]
    assert second.next_cursor is None
    assert second.total == 3


async def test_a_forged_cursor_is_refused(repo: PostgresRolesRepository) -> None:
    with pytest.raises(InvalidCursorError):
        await repo.buyers_page(BuyerFilters(), "not-a-cursor", 10)


async def test_buyer_filters_narrow_matched_but_not_total(repo: PostgresRolesRepository) -> None:
    by_sector = await repo.buyers_page(BuyerFilters(sectors=("Dental",)), None, 10)
    by_geography = await repo.buyers_page(BuyerFilters(geographies=("Saudi Arabia",)), None, 10)
    by_region = await repo.buyers_page(BuyerFilters(geographies=("GCC",)), None, 10)
    by_check = await repo.buyers_page(BuyerFilters(check_size=Range(min=15e6)), None, 10)
    by_ebitda = await repo.buyers_page(BuyerFilters(min_ebitda=Range(min=1e5)), None, 10)

    assert [r.name for r in by_sector.rows] == ["Alpha Capital", "Gamma Fund"]
    assert (by_sector.matched, by_sector.total) == (2, 3)
    assert [r.name for r in by_geography.rows] == ["Beta Partners"]
    assert [r.name for r in by_region.rows] == ["Alpha Capital"]
    # Gamma has no check size recorded, so it overlaps any range.
    assert [r.name for r in by_check.rows] == ["Beta Partners", "Gamma Fund"]
    # An unknown EBITDA floor only passes an open range.
    assert [r.name for r in by_ebitda.rows] == ["Alpha Capital"]


async def test_text_search_needs_every_word_and_reads_notes_and_contacts(
    repo: PostgresRolesRepository,
) -> None:
    by_note = await repo.buyers_page(BuyerFilters(text="CLINICS alpha"), None, 10)
    by_contact = await repo.buyers_page(BuyerFilters(text="rania"), None, 10)
    miss = await repo.buyers_page(BuyerFilters(text="clinics beta"), None, 10)
    wildcard = await repo.buyers_page(BuyerFilters(text="%"), None, 10)

    assert [r.name for r in by_note.rows] == ["Alpha Capital"]
    assert [r.name for r in by_contact.rows] == ["Alpha Capital"]
    assert miss.rows == ()
    assert wildcard.rows == ()


async def test_sellers_map_geography_signal_and_contacts(repo: PostgresRolesRepository) -> None:
    page = await repo.sellers_page(SellerFilters(), None, 10)

    assert [r.name for r in page.rows] == ["Alpha Capital", "Beta Partners", "Gamma Fund"]
    alpha, beta, gamma = page.rows
    assert (alpha.open_to_selling, beta.open_to_selling, gamma.open_to_selling) == (
        "Warm intro",
        "Unknown",
        "Interested",
    )
    assert (alpha.geography, gamma.geography) == ("GCC", "Levant")
    assert gamma.sector == "Dental, Retail"
    assert alpha.contact_ids == ("p0",)
    assert page.options.sectors == ("Dental", "Retail")
    assert page.options.geographies == ("GCC", "Levant")


async def test_seller_filters(repo: PostgresRolesRepository) -> None:
    unknown = await repo.sellers_page(SellerFilters(open_to_selling=("Unknown",)), None, 10)
    interested = await repo.sellers_page(SellerFilters(open_to_selling=("Interested",)), None, 10)
    revenue = await repo.sellers_page(SellerFilters(revenue=Range(min=1e6, max=10e6)), None, 10)
    sector = await repo.sellers_page(SellerFilters(sectors=("Retail",)), None, 10)
    geography = await repo.sellers_page(SellerFilters(geographies=("Levant",)), None, 10)

    assert [r.name for r in unknown.rows] == ["Beta Partners"]
    assert [r.name for r in interested.rows] == ["Gamma Fund"]
    assert [r.name for r in revenue.rows] == ["Alpha Capital"]
    assert [r.name for r in sector.rows] == ["Beta Partners", "Gamma Fund"]
    assert [r.name for r in geography.rows] == ["Gamma Fund"]


async def test_single_role_reads_and_unknown_ids(repo: PostgresRolesRepository) -> None:
    page = await repo.buyers_page(BuyerFilters(), None, 1)
    role = await repo.buyer(page.rows[0].id)

    assert role is not None
    assert role.etag == page.rows[0].etag
    assert await repo.buyer("not-a-uuid") is None
    assert await repo.seller("00000000-0000-0000-0000-000000000000") is None


async def test_sign_in_matches_email_case_insensitively_and_skips_inactive_people(
    repo: PostgresRolesRepository,
) -> None:
    jules = await repo.member_by_email("jules@wusoolcapital.com")

    assert jules is not None
    assert (jules.id, jules.email) == ("u1", "jules@wusoolcapital.com")
    assert await repo.member_by_email("gone@wusoolcapital.com") is None
    assert await repo.member_by_email("nobody@wusoolcapital.com") is None
