"""Normalisation and key composition. Pure functions, no fixtures — the
cases here are the real shapes a public form yields.
"""

import pytest

from app.modules.lead_magnets.domain.shared.dedup import (
    domain_matches,
    idempotency_key,
    normalise_domain,
    normalise_email,
    normalise_name,
    org_key,
    person_key,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.com", "example.com"),
        ("EXAMPLE.COM", "example.com"),
        ("  example.com  ", "example.com"),
        ("www.example.com", "example.com"),
        ("https://example.com", "example.com"),
        ("http://WWW.Example.com/path?utm=x", "example.com"),
        ("https://example.com:8443/", "example.com"),
        # A copied address can carry the root's trailing dot.
        ("example.com.", "example.com"),
        ("https://sub.example.com", "sub.example.com"),
        # "www" only counts as a leading label, never mid-host.
        ("https://wwwexample.com", "wwwexample.com"),
        (None, ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalise_domain(raw: str | None, expected: str) -> None:
    assert normalise_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Acme Trading LLC", "acme trading"),
        ("Acme Trading L.L.C.", "acme trading"),
        ("Acme Trading FZ-LLC", "acme trading"),
        ("Acme  Trading   FZCO", "acme trading"),
        ("Acme Trading FZE", "acme trading"),
        ("Acme Trading Ltd", "acme trading"),
        ("Acme Trading Limited", "acme trading"),
        ("Acme Trading WLL", "acme trading"),
        ("Acme Trading DMCC", "acme trading"),
        ("Acme Trading Inc", "acme trading"),
        ("\tAcme\nTrading\t", "acme trading"),
        # Two suffixes is not a shape anyone intends, but a form allows it.
        ("Acme Holdings Ltd LLC", "acme holdings"),
        ("Acme & Co LLC", "acme & co"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalise_name(raw: str | None, expected: str) -> None:
    assert normalise_name(raw) == expected


def test_normalise_name_never_strips_the_whole_name() -> None:
    """A company actually called "Limited" must survive — stripping to an
    empty key would collide with every other empty-name submission."""
    assert normalise_name("Limited") == "limited"
    assert normalise_name("LLC") == "llc"


def test_normalise_email() -> None:
    assert normalise_email("  Founder@Example.COM ") == "founder@example.com"
    assert normalise_email(None) == ""


def test_normalise_email_keeps_plus_tags_and_dots() -> None:
    """Provider-specific cleverness would merge two addresses a person may
    genuinely treat as separate."""
    assert normalise_email("First.Last+wusool@Gmail.com") == "first.last+wusool@gmail.com"


def test_org_key_is_domain_and_name() -> None:
    """Domain alone would permanently merge two brands on one holdco
    domain — the reason marking `organizations.domains` unique was rejected.
    """
    one = org_key(domain="https://holdco.com", name="Brand One LLC")
    two = org_key(domain="https://holdco.com", name="Brand Two LLC")
    assert one == "holdco.com|brand one"
    assert one != two


def test_org_key_matches_across_input_spellings() -> None:
    assert org_key(domain="WWW.Acme.com/contact", name="Acme  Trading L.L.C.") == org_key(
        domain="https://acme.com", name="acme trading"
    )


def test_person_key_is_the_lowercased_email() -> None:
    assert person_key(" Founder@Acme.com ") == "founder@acme.com"


def test_idempotency_key_carries_the_tool() -> None:
    key = idempotency_key(
        tool="readiness",
        email="Founder@Acme.com",
        domain="https://www.acme.com",
    )
    assert key == "readiness|founder@acme.com|acme.com"


def test_idempotency_key_separates_tools_but_org_key_does_not() -> None:
    """The tool belongs in the submission key only. In the entity key it
    would produce one organisation per tool — the opposite of dedup."""
    args = {"email": "f@acme.com", "domain": "acme.com"}
    assert idempotency_key(tool="valuation", **args) != idempotency_key(tool="readiness", **args)
    assert org_key(domain="acme.com", name="Acme") == org_key(domain="acme.com", name="Acme")


def test_domain_matches_ignores_scheme_and_case() -> None:
    assert domain_matches(["Example.com", "other.com"], "https://WWW.Example.com/path")


def test_domain_matches_is_false_for_no_overlap() -> None:
    assert not domain_matches(["other.com"], "example.com")


def test_domain_matches_is_false_for_an_empty_domain() -> None:
    """An empty/missing domain is never a wildcard match against every
    candidate's domain list."""
    assert not domain_matches(["example.com"], None)
    assert not domain_matches(["example.com"], "")
    assert not domain_matches([], "example.com")


def test_idempotency_key_is_identical_for_a_repeat_visit() -> None:
    """No `submission_id` component — a second genuine visit from the same
    person, for the same tool, must produce the exact same key so it
    collides on purpose (`ToolRunsRepository.start` then tells `"replay"`
    from `"duplicate"` by comparing `payload.submission_id` on the
    colliding row) rather than sailing through as a new person the way it
    did when `submission_id` was part of this key."""
    args = {"tool": "readiness", "email": "f@acme.com", "domain": "acme.com"}
    assert idempotency_key(**args) == idempotency_key(**args)
