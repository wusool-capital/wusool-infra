"""`resolve_known` — the controlled-vocabulary/unrestricted-term table
`providers/google_places/client.py::_resolve_geography` checks before ever
calling Google's Geocoding API. Pure function, no network."""

from app.modules.discovery.domain.geography import GeographyScope, resolve_known


def test_gcc_wide_resolves_to_the_six_gcc_states() -> None:
    scope = resolve_known("GCC-wide")

    assert scope is not None
    assert scope.unrestricted is False
    assert scope.countries == frozenset(
        {"United Arab Emirates", "Saudi Arabia", "Kuwait", "Bahrain", "Qatar", "Oman"}
    )
    assert scope.viewport is not None


def test_gcc_synonyms_resolve_to_the_same_scope() -> None:
    """Real controlled-vocabulary spelling ("GCC-wide") plus the plain
    synonyms a free-text/meeting-notes-derived value might use."""
    canonical = resolve_known("GCC-wide")

    for synonym in ("gcc", "GCC", "Gulf", "gulf cooperation council"):
        assert resolve_known(synonym) == canonical


def test_mena_resolves_to_a_multi_country_region() -> None:
    scope = resolve_known("MENA")

    assert scope is not None
    assert "Egypt" in scope.countries
    assert "United Arab Emirates" in scope.countries
    assert "Germany" not in scope.countries
    assert scope.unrestricted is False


def test_global_resolves_to_unrestricted_with_no_countries() -> None:
    scope = resolve_known("Global")

    assert scope == GeographyScope(unrestricted=True)


def test_unrestricted_synonyms_all_resolve() -> None:
    for term in ("worldwide", "Worldwide", "international", "any", "anywhere"):
        assert resolve_known(term) == GeographyScope(unrestricted=True)


def test_resolution_is_whitespace_and_case_insensitive() -> None:
    assert resolve_known("  gcc-wide  ") == resolve_known("GCC-Wide")


def test_an_unrecognized_token_resolves_to_none() -> None:
    """The caller's signal to fall back to a live geocode call — a single
    country name like "UAE" is deliberately not in this table, since it
    already geocodes correctly on its own (verified live)."""
    assert resolve_known("UAE") is None
    assert resolve_known("Some Random City") is None
