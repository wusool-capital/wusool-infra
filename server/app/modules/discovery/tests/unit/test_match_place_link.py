"""`_match_place_link` — resolves a lead's `source_url` to a specific
Google Maps listing rather than the shared, unresolved search URL every
lead in a batch would otherwise fall back to. A previously-required
trailing slash silently rejected two real link shapes Google Maps returns
(no trailing slash at all, and a trailing `?query` string).
"""

from app.modules.discovery.providers.firecrawl.client import _match_place_link


def test_matches_a_place_link_with_a_trailing_slash() -> None:
    links = ["https://www.google.com/maps/place/Acme+Clinic/@40.7,-74.0,15z"]

    assert _match_place_link("Acme Clinic", links) == links[0]


def test_matches_a_place_link_with_no_trailing_slash() -> None:
    links = ["https://www.google.com/maps/place/Acme+Clinic"]

    assert _match_place_link("Acme Clinic", links) == links[0]


def test_matches_a_place_link_followed_by_a_query_string() -> None:
    links = ["https://www.google.com/maps/place/Acme+Clinic?entry=ttu"]

    assert _match_place_link("Acme Clinic", links) == links[0]


def test_returns_none_when_no_link_matches_the_name() -> None:
    links = ["https://www.google.com/maps/place/Beta+Co/"]

    assert _match_place_link("Acme Clinic", links) is None


def test_ignores_a_non_google_maps_link() -> None:
    links = ["https://example.com/maps/place/Acme+Clinic/"]

    assert _match_place_link("Acme Clinic", links) is None


def test_returns_none_with_no_links() -> None:
    assert _match_place_link("Acme Clinic", []) is None
