from app.modules.interactions.domain.linking import (
    Ambiguity,
    PersonRef,
    RecordDirectory,
    resolve_link,
)


def _directory(
    people: dict[str, tuple[PersonRef, ...]] | None = None,
    orgs: dict[str, tuple[str, ...]] | None = None,
) -> RecordDirectory:
    return RecordDirectory(people_by_email=people or {}, org_ids_by_domain=orgs or {})


def test_a_unique_person_links_with_their_own_organization() -> None:
    directory = _directory(
        people={"sara@acme.com": (PersonRef("p1", "o-from-person"),)},
        orgs={"acme.com": ("o-from-domain",)},
    )

    result = resolve_link("sara@acme.com", directory)

    assert (result.person_id, result.organization_id, result.ambiguity) == (
        "p1",
        "o-from-person",
        None,
    )


def test_a_person_without_an_organization_falls_back_to_the_domain() -> None:
    directory = _directory(
        people={"sara@acme.com": (PersonRef("p1", None),)}, orgs={"acme.com": ("o1",)}
    )

    result = resolve_link("sara@acme.com", directory)

    assert (result.person_id, result.organization_id) == ("p1", "o1")


def test_an_unknown_person_still_gets_the_organization_for_their_domain() -> None:
    result = resolve_link("new@acme.com", _directory(orgs={"acme.com": ("o1",)}))

    assert (result.person_id, result.organization_id, result.ambiguity) == (None, "o1", None)


def test_a_subdomain_matches_its_parent_organization() -> None:
    result = resolve_link("news@mail.acme.com", _directory(orgs={"acme.com": ("o1",)}))

    assert result.organization_id == "o1"


def test_the_most_specific_domain_wins() -> None:
    orgs = {"eu.acme.com": ("o-eu",), "acme.com": ("o-global",)}

    assert resolve_link("x@eu.acme.com", _directory(orgs=orgs)).organization_id == "o-eu"


def test_an_address_shared_by_several_persons_links_nothing() -> None:
    directory = _directory(
        people={"info@acme.com": (PersonRef("p1", "o1"), PersonRef("p2", "o2"))},
        orgs={"acme.com": ("o1",)},
    )

    result = resolve_link("info@acme.com", directory)

    assert (result.person_id, result.organization_id) == (None, None)
    assert result.ambiguity is Ambiguity.SHARED_EMAIL


def test_a_domain_shared_by_two_organizations_links_no_organization() -> None:
    directory = _directory(
        people={"sara@acme.com": (PersonRef("p1", None),)}, orgs={"acme.com": ("o1", "o2")}
    )

    result = resolve_link("sara@acme.com", directory)

    assert (result.person_id, result.organization_id) == ("p1", None)
    assert result.ambiguity is Ambiguity.SHARED_DOMAIN


def test_a_shared_child_domain_is_not_resolved_by_its_parent() -> None:
    orgs = {"eu.acme.com": ("o1", "o2"), "acme.com": ("o-global",)}

    result = resolve_link("x@eu.acme.com", _directory(orgs=orgs))

    assert (result.organization_id, result.ambiguity) == (None, Ambiguity.SHARED_DOMAIN)


def test_an_address_nobody_knows_resolves_to_nothing() -> None:
    result = resolve_link("who@nowhere.org", _directory())

    assert (result.person_id, result.organization_id, result.ambiguity) == (None, None, None)
