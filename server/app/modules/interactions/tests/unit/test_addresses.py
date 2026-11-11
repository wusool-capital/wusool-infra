from app.modules.interactions.domain.addresses import (
    domain_of,
    is_internal,
    org_domain_candidates,
    team_member_of,
)


def test_domain_of_takes_the_part_after_the_last_at() -> None:
    assert domain_of("sara@news.acme.com") == "news.acme.com"


def test_both_company_domains_are_internal() -> None:
    assert is_internal("hugo@wusoolcapital.com")
    assert is_internal("hugo@dopaminecap.com")
    assert not is_internal("hugo@acme.com")


def test_alias_addresses_fold_into_one_team_member() -> None:
    assert team_member_of("hugo@dopaminecap.com") == "hugo@wusoolcapital.com"
    assert team_member_of("hugo@wusoolcapital.com") == "hugo@wusoolcapital.com"


def test_outside_addresses_are_left_alone() -> None:
    assert team_member_of("sara@acme.com") == "sara@acme.com"


def test_subdomains_try_each_parent_but_never_the_bare_tld() -> None:
    assert org_domain_candidates("news.eu.acme.com") == (
        "news.eu.acme.com",
        "eu.acme.com",
        "acme.com",
    )
    assert org_domain_candidates("Acme.com") == ("acme.com",)
