"""Resolves a `geography` string (a buyer's `target_region`/`target_country`
value — see `ddl_commands.api.buyers.BUYER_ROLE_FIELDS` — or free text) to a
concrete search scope, for the handful of values a live geocode call gets
wrong or can't answer at all.

Single countries geocode correctly via Google's Geocoding API (verified
live, 2026-09-15) — those stay on the live-geocode path in
`providers/google_places/client.py`. Only two kinds of token need resolving
here, without a network call:

- A real multi-country region with no single coordinate (`GCC-wide`).
  Geocoding the bare string is actively wrong, not just unhelpful: Google
  matches it to an unrelated US institution commonly abbreviated the same
  way — verified live, `"GCC"` and `"GCC-wide, Global"` both resolve to
  "Glendale Community College", 1500 N Verdugo Rd, Glendale, CA, with
  `status: OK` and no error. `providers/google_places/client.py`'s own
  type/partial-match validation independently rejects that specific
  response (its `types` are POI/establishment, not a country or admin
  area) — this table exists so the real GCC states are still searched
  after that rejection, not just so the false match is blocked.
- An explicit "no restriction" term (`Global`), which is a real request
  for an unrestricted search, not an unresolvable one, and should never be
  logged or treated the same as "couldn't figure out what this means."

GCC, MENA and MENATP are the `target_region` blocs covered here; the table
is a plain dict, trivially extended if another value proves common enough to
be worth hardcoding rather than falling through to a live geocode.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LatLng:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Rectangle:
    low: LatLng
    high: LatLng


@dataclass(frozen=True)
class GeographyScope:
    """`countries`: a result's resolved country must be in this set to pass
    the post-search filter — empty means "nothing resolved to a country,"
    not "no restriction," and the caller must check `unrestricted`
    separately to tell those apart in logs. `viewport`: an optional
    `locationRestriction` hint; `countries` is what actually enforces
    correctness, so a missing viewport only widens the initial Places
    search, it never lets a wrong-country result through. `unrestricted`:
    an explicit "search anywhere" request (e.g. `"Global"`) — distinct from
    the zero-value default, which means "couldn't resolve this at all."
    """

    countries: frozenset[str] = field(default_factory=frozenset)
    viewport: Rectangle | None = None
    unrestricted: bool = False


_UNRESTRICTED_TOKENS = frozenset({"global", "worldwide", "international", "any", "anywhere"})

# Long-form country names exactly as Google's Geocoding API returns them
# (`address_components[].long_name` where `types` includes `"country"`) —
# each verified individually live, not guessed, since the post-search
# filter is an exact string match against this set.
_GCC_COUNTRIES = frozenset(
    {"United Arab Emirates", "Saudi Arabia", "Kuwait", "Bahrain", "Qatar", "Oman"}
)
# A single rectangle roughly covering the Arabian Peninsula — wide enough to
# contain all 6 GCC states with margin. Precision doesn't matter here the
# way `_GCC_COUNTRIES` does: this only biases which candidates Places
# returns in the first place, `_GCC_COUNTRIES` is what actually decides
# which of them are kept.
_GCC_VIEWPORT = Rectangle(
    low=LatLng(latitude=16.0, longitude=34.0), high=LatLng(latitude=30.5, longitude=60.0)
)

_MENA_COUNTRIES = frozenset(
    {
        "Algeria",
        "Bahrain",
        "Djibouti",
        "Egypt",
        "Iran",
        "Iraq",
        "Israel",
        "Jordan",
        "Kuwait",
        "Lebanon",
        "Libya",
        "Morocco",
        "Oman",
        "Palestine",
        "Qatar",
        "Saudi Arabia",
        "Syria",
        "Tunisia",
        "United Arab Emirates",
        "Yemen",
    }
)
_MENA_VIEWPORT = Rectangle(
    low=LatLng(latitude=11.0, longitude=-13.0), high=LatLng(latitude=40.0, longitude=63.5)
)

# MENA plus Turkey and Pakistan. An abbreviation, so it must never reach a live geocode.
_MENATP_COUNTRIES = _MENA_COUNTRIES | {"Türkiye", "Turkey", "Pakistan"}
_MENATP_VIEWPORT = Rectangle(
    low=LatLng(latitude=11.0, longitude=-13.0), high=LatLng(latitude=42.5, longitude=77.5)
)

# The buyer `target_region` options, owned here because this module resolves them.
# Drift against `ddl_commands`' field spec: `tests/test_discrepancies_region_vocabulary.py`.
TARGET_REGION_OPTIONS: tuple[str, ...] = (
    "GCC",
    "MENA",
    "MENATP",
    "Africa",
    "Asia",
    "Europe",
    "Southeast Asia",
    "Latin America",
    "Emerging Markets",
    "Global",
)

_KNOWN_REGIONS: dict[str, GeographyScope] = {
    "gcc": GeographyScope(countries=_GCC_COUNTRIES, viewport=_GCC_VIEWPORT),
    "gcc-wide": GeographyScope(countries=_GCC_COUNTRIES, viewport=_GCC_VIEWPORT),
    "gulf": GeographyScope(countries=_GCC_COUNTRIES, viewport=_GCC_VIEWPORT),
    "gulf cooperation council": GeographyScope(countries=_GCC_COUNTRIES, viewport=_GCC_VIEWPORT),
    "mena": GeographyScope(countries=_MENA_COUNTRIES, viewport=_MENA_VIEWPORT),
    "middle east and north africa": GeographyScope(
        countries=_MENA_COUNTRIES, viewport=_MENA_VIEWPORT
    ),
    # Treated as a MENA synonym, not a stricter Middle-East-only list
    # (excluding North Africa) — the distinction is genuinely fuzzy in
    # casual usage, and the country filter degrading to a few extra
    # eligible countries is a minor cost. Not just a cheap addition: left
    # off this table, "Middle East" geocodes live to a real
    # `colloquial_area` result with no country component at all (verified
    # live) — `_ACCEPTED_GEOCODE_TYPES` accepts it (it's a real place, not
    # a false match), so it silently produces a viewport with zero country
    # enforcement, the exact "viewport alone isn't a real guarantee" gap
    # this module exists to close. Routing it through this table instead
    # gives it the same real country-list enforcement as GCC/MENA.
    "middle east": GeographyScope(countries=_MENA_COUNTRIES, viewport=_MENA_VIEWPORT),
    "menatp": GeographyScope(countries=_MENATP_COUNTRIES, viewport=_MENATP_VIEWPORT),
    # Not a place, so there is nothing to geocode and nothing to enforce: it
    # describes a class of economy, not an area. Left to geocode it would be
    # another "GCC" -- a plausible-looking result for something that is not a
    # location. Resolved as unrestricted, explicitly, rather than by accident.
    "emerging markets": GeographyScope(unrestricted=True),
}


def resolve_known(token: str) -> GeographyScope | None:
    """Returns a `GeographyScope` for a token this module can resolve
    without a network call, or `None` if the token isn't one of these —
    the caller falls back to a live geocode for anything not covered here.
    A token resolves to exactly one of a multi-country region or an
    explicit unrestricted scope, never both.

    What belongs in this table, after the 2026-09-26 region/country split:
    abbreviations and economic blocs, not every region. `GCC` broke because
    it is an abbreviation that geocodes to a real, wrong place; `Emerging
    Markets` is not a location at all. Ordinary geographic names — Africa,
    Europe, Southeast Asia — geocode correctly and are checked against
    `_ACCEPTED_GEOCODE_TYPES`, so they do not need entries here. The buyer
    vocabulary now spells regions out in full (Southeast Asia, not SEA),
    which is what keeps the abbreviation hazard from coming back.
    """
    normalized = token.strip().lower()
    if normalized in _UNRESTRICTED_TOKENS:
        return GeographyScope(unrestricted=True)
    return _KNOWN_REGIONS.get(normalized)


# Spellings of one country seen across Attio fields (`hq_country`, `geographic_focus`,
# `target_country`) and Google's geocoder; all lowercase.
_COUNTRY_ALIASES: tuple[frozenset[str], ...] = (
    frozenset({"united arab emirates", "uae", "u.a.e."}),
    frozenset({"saudi arabia", "ksa", "saudi"}),
    frozenset({"united kingdom", "uk", "u.k."}),
    frozenset({"united states", "usa", "us", "u.s."}),
    frozenset({"türkiye", "turkey"}),
    frozenset({"hong kong", "hong kong sar"}),
    frozenset({"palestine", "palestinian authority"}),
)


def country_spellings(country: str) -> frozenset[str]:
    """Every lowercase spelling of `country`, itself included."""
    normalized = country.strip().lower()
    for group in _COUNTRY_ALIASES:
        if normalized in group:
            return group
    return frozenset({normalized})
