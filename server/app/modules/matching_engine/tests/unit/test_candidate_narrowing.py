"""`CandidateNarrowing.from_buyer` — what the SQL load is allowed to rule out,
derived from the buyer role's own CRM fields only.
"""

from dataclasses import replace

from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.narrowing import CandidateNarrowing
from app.modules.matching_engine.domain.requirements import HardRequirement, RequirementProfile
from app.modules.utilities.domain.money import Money


def _buyer(**overrides: object) -> BuyerContext:
    base = BuyerContext(
        buyer_role_id="buyer-1",
        org_attio_id="org-1",
        org_name="Acme Capital",
        model=None,
        mandate_status=None,
        ebitda_floor=None,
        check_size_min=None,
        check_size_max=None,
        ev_ceiling=None,
        deal_structure_tolerance=None,
        earnout_tolerance=None,
        profitable_only=None,
        investment_strategy=None,
        notes=None,
        contact_person_id=None,
    )
    return replace(base, **overrides)


def _profile_stating_geography(value: str) -> RequirementProfile:
    stated = HardRequirement("geography", value, "advisor_context", "high", True)
    return RequirementProfile([stated], [], None, None, {}, 0.8, "model", 1)


def test_empty_buyer_narrows_nothing() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer())

    assert narrowing == CandidateNarrowing()
    assert not narrowing.narrows_geography


def test_vertical_is_lower_cased_and_trimmed() -> None:
    assert CandidateNarrowing.from_buyer(_buyer(target_vertical=" Pharma Tech ")).vertical == (
        "pharma tech"
    )


def test_ev_ceiling_comes_from_money_amount_and_check_size_never_narrows() -> None:
    narrowing = CandidateNarrowing.from_buyer(
        _buyer(
            check_size_min=Money(5_000_000.0, "USD"),
            check_size_max=Money(15_000_000.0, "USD"),
            ev_ceiling=Money(40_000_000.0, "USD"),
        )
    )

    assert narrowing == CandidateNarrowing(ev_ceiling=40_000_000.0)


def test_gcc_region_expands_to_its_countries_and_keeps_the_region() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_region=["GCC"]))

    assert "saudi arabia" in narrowing.countries
    assert "gcc" in narrowing.regions


def test_country_only_buyer_also_accepts_an_overlapping_seller_region() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_country=["Saudi Arabia"]))

    assert {"saudi arabia", "ksa"} <= narrowing.countries
    assert {"gcc", "mena"} <= narrowing.regions


def test_unrelated_country_does_not_accept_gulf_regions() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_country=["Pakistan"]))

    # MENATP is the one region that includes Pakistan.
    assert narrowing.regions == frozenset({"menatp"})


def test_unrestricted_region_disables_geography() -> None:
    narrowing = CandidateNarrowing.from_buyer(
        _buyer(target_region=["GCC", "Global"], target_country=["Egypt"])
    )

    assert not narrowing.narrows_geography


def test_unresolvable_region_disables_geography() -> None:
    narrowing = CandidateNarrowing.from_buyer(
        _buyer(target_region=["Africa"], target_country=["Egypt"])
    )

    assert not narrowing.narrows_geography


def test_gulf_country_also_accepts_its_common_abbreviations_and_region_spellings() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_country=["United Arab Emirates"]))

    assert {"uae", "u.a.e."} <= narrowing.countries
    assert {"gcc", "gulf", "middle east"} <= narrowing.regions


def test_stated_unresolvable_region_disables_geography_not_a_literal_country() -> None:
    profile = _profile_stating_geography("Europe")
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_region=["GCC"]), profile)

    assert not narrowing.narrows_geography


def test_country_aliases_cover_turkiye() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(target_country=["Turkey"]))

    assert {"turkey", "türkiye"} <= narrowing.countries


def test_stated_menatp_narrows_to_its_countries_including_turkiye() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(), _profile_stating_geography("MENATP"))

    assert {"pakistan", "türkiye", "turkey", "egypt"} <= narrowing.countries
    assert "europe" not in narrowing.countries


def test_stated_country_alias_is_kept_as_a_country() -> None:
    narrowing = CandidateNarrowing.from_buyer(_buyer(), _profile_stating_geography("KSA"))

    assert {"ksa", "saudi arabia"} <= narrowing.countries
