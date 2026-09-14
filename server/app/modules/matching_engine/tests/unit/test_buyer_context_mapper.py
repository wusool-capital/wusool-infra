"""`to_buyer_context` — plain ORM-row-to-dataclass mapping, no DB session
needed (constructed in-memory, `organization` assigned directly rather than
through a relationship load). Covers the fields found missing entirely on
2026-09-14: `target_geography`, `ebitda_ceiling`, and the `organizations`
columns beyond `hq_country`/`sector_focus` — a buyer with a real, populated
`target_geography` still produced an unrestricted seller search, since
`BuyerContext` never carried it past this mapper at all.
"""

from app.models import BuyerRole, Organization
from app.modules.matching_engine.persistence.mappers import to_buyer_context


def _buyer_role() -> BuyerRole:
    role = BuyerRole(
        org_attio_id="org-1",
        target_geography=["GCC-wide", "Global"],
        ebitda_ceiling={"amount": 5_000_000.0, "currency": "USD"},
        notable_investments="Acquired three regional fintechs since 2023.",
        key_personnel="Jane Doe, Managing Partner",
        acquisition_enrichment="Active in mid-market roll-ups.",
        prior_gcc_acquisition="Yes, two prior GCC acquisitions.",
    )
    role.organization = Organization(
        attio_id="org-1",
        name="Investcorp",
        hq_country="United Kingdom",
        sector_focus=["Healthcare"],
        description="Global alternative investment firm.",
        type=["Private Equity"],
        categories=["Alternative Investments"],
        region="Europe",
    )
    return role


def test_maps_target_geography_and_ebitda_ceiling() -> None:
    context = to_buyer_context(_buyer_role())

    assert context.target_geography == ["GCC-wide", "Global"]
    assert context.ebitda_ceiling is not None
    assert context.ebitda_ceiling.amount == 5_000_000.0


def test_maps_the_qualitative_buyer_role_fields() -> None:
    context = to_buyer_context(_buyer_role())

    assert context.notable_investments == "Acquired three regional fintechs since 2023."
    assert context.key_personnel == "Jane Doe, Managing Partner"
    assert context.acquisition_enrichment == "Active in mid-market roll-ups."
    assert context.prior_gcc_acquisition == "Yes, two prior GCC acquisitions."


def test_maps_organization_fields_beyond_hq_country_and_sector_focus() -> None:
    context = to_buyer_context(_buyer_role())

    assert context.org_hq_country == "United Kingdom"
    assert context.org_sector_focus == ["Healthcare"]
    assert context.org_description == "Global alternative investment firm."
    assert context.org_type == ["Private Equity"]
    assert context.org_categories == ["Alternative Investments"]
    assert context.org_region == "Europe"


def test_empty_target_geography_maps_to_an_empty_list_not_none() -> None:
    role = BuyerRole(org_attio_id="org-2", target_geography=[])
    role.organization = Organization(attio_id="org-2", name="Blank Co")

    context = to_buyer_context(role)

    assert context.target_geography == []


def test_missing_ebitda_ceiling_maps_to_none() -> None:
    role = BuyerRole(org_attio_id="org-2", ebitda_ceiling=None)
    role.organization = Organization(attio_id="org-2", name="Blank Co")

    context = to_buyer_context(role)

    assert context.ebitda_ceiling is None
