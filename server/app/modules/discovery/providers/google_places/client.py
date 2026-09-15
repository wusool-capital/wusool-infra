"""Real Google Places implementation of `LeadSearchClient`. Replaces
`FirecrawlMapsClient` — same `discovery`-owns-lead-search rationale, now
against Google's typed Places API (New) + Geocoding API instead of scraping
a Google Maps search page.

`_resolve_geography` splits `geography` on commas and resolves each token —
via `domain.geography.resolve_known`'s controlled-vocabulary table first
(multi-country regions and explicit "no restriction" terms a single geocode
call can't answer correctly, e.g. `"GCC-wide"`), then a live `_geocode` call
for anything left — into one `GeographyScope`: a country set for the
post-search filter, and at most one `locationRestriction` viewport (see that
function's own docstring for why more than one collapses to none). A
`_geocode` result that isn't validated as a real place — anything but a
`status: "OK"`, non-`country`/`administrative_area`/`locality`-shaped, or
Google's own `partial_match: true` — is rejected before it ever reaches
`GeographyScope`, not just logged: a bare word like `"GCC"` confidently
matches an unrelated US institution abbreviated the same way (verified
live), and that match must never silently become a locationRestriction/
country filter. A `geography` that resolves to nothing at all (empty string,
or every token rejected) falls back to an unrestricted, unfiltered search —
the same unbounded behavior the old Firecrawl scrape always had.

`_search_places` runs the actual text search, sharing one
`aiohttp.ClientSession` with the geocode calls above it.
"""

import logging
from urllib.parse import quote

import aiohttp

from app.modules.discovery.domain.geography import (
    GeographyScope,
    LatLng,
    Rectangle,
    resolve_known,
)
from app.modules.discovery.domain.leads import DiscoveredLead, filter_excluded_leads
from app.modules.discovery.providers.google_places.schemas import (
    GeocodeResponse,
    LocationRestriction,
    LocationRestrictionRectangle,
    Place,
    PlaceLatLng,
    PlacesSearchRequest,
    PlacesSearchResponse,
)

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
# `websiteUri` alone puts every request on Places' Enterprise SKU tier, so
# every other field below rides along free — see the plan's billing note.
# Deliberately not requested: `places.id`/`places.location` (this module has
# no dedupe by design — see the README's "Why no dedupe here"),
# `places.rating`/`places.userRatingCount` (no consumer today).
_FIELD_MASK = (
    "places.displayName,places.formattedAddress,places.googleMapsUri,"
    "places.primaryTypeDisplayName,places.websiteUri,"
    "places.addressComponents,places.types"
)
# A synchronous, human-triggered search — aiohttp's 300s default would leave
# a Slack "Searching for potential sellers…" placeholder hanging far longer
# than a hung call is ever worth waiting on.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
# Costs the same request as `limit=3` — Places bills per call, not per
# result — so ask for the max and let `filter_excluded_leads` + `[:limit]`
# narrow it down without spending a second call.
_PAGE_SIZE = 20
# Google's Geocoding API `types` taxonomy for a real place hierarchy —
# country down to city/town — as opposed to a business/POI/establishment
# match. `colloquial_area` covers a real supra-national region Google itself
# recognizes (e.g. "Middle East") with no single country of its own.
# Deliberately excludes `street_address`/`route`/`point_of_interest`/
# `establishment`/etc. — those are exactly what a bare business term like
# "GCC" false-matches (verified live: "GCC" -> Glendale Community College,
# `types: ["book_store","establishment","point_of_interest","store",
# "university"]`).
_ACCEPTED_GEOCODE_TYPES = frozenset(
    {
        "country",
        "administrative_area_level_1",
        "administrative_area_level_2",
        "locality",
        "sublocality",
        "postal_town",
        "colloquial_area",
    }
)


def _place_country(place: Place) -> str | None:
    for component in place.addressComponents:
        if "country" in component.types and component.longText:
            return component.longText
    return None


class GooglePlacesClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int, exclude_terms: tuple[str, ...] = ()
    ) -> list[DiscoveredLead]:
        text_query = f"{industry} companies {geography}".strip()

        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            scope = await self._resolve_geography(session, geography)
            places = await self._search_places(
                session, text_query=text_query, location_restriction=scope.viewport
            )
        if places is None:
            return []

        if scope.countries:
            kept: list[Place] = []
            dropped = 0
            unverified = 0
            expected = ",".join(sorted(scope.countries))
            for p in places:
                place_country = _place_country(p)
                if place_country is None:
                    # Can't evaluate what Places didn't tell us — keeping
                    # it (rather than dropping) trades a possible
                    # out-of-country lead for never discarding one we
                    # simply can't check, but it must still show up in
                    # logs as a known gap in the geography guarantee.
                    unverified += 1
                    kept.append(p)
                elif place_country in scope.countries:
                    kept.append(p)
                else:
                    dropped += 1
            if dropped:
                logger.info(
                    "discovery_leads_out_of_country query=%s expected_countries=%s dropped=%d",
                    text_query,
                    expected,
                    dropped,
                )
            if unverified:
                logger.info(
                    "discovery_leads_unverified_country query=%s expected_countries=%s "
                    "kept_without_verification=%d",
                    text_query,
                    expected,
                    unverified,
                )
            places = kept

        leads = [lead for p in places if (lead := self._to_lead(p, text_query)) is not None]
        logger.info(
            "discovery_places_search_completed query=%s businesses_found=%d",
            text_query,
            len(leads),
        )

        # Filter before slicing to `limit` — an excluded lead must not
        # consume a slot a genuinely qualifying one could have filled.
        filtered = filter_excluded_leads(leads, exclude_terms)
        excluded_count = len(leads) - len(filtered)
        if excluded_count:
            logger.info(
                "discovery_leads_excluded query=%s excluded=%d exclude_terms=%s",
                text_query,
                excluded_count,
                exclude_terms,
            )
        return filtered[:limit]

    @staticmethod
    def _to_lead(place: Place, text_query: str) -> DiscoveredLead | None:
        name = place.displayName.text if place.displayName else None
        if not name:
            return None
        return DiscoveredLead(
            name=name,
            source_url=place.googleMapsUri
            or f"https://www.google.com/maps/search/{quote(text_query)}",
            address=place.formattedAddress,
            category=place.primaryTypeDisplayName.text if place.primaryTypeDisplayName else None,
            country=_place_country(place),
            website=place.websiteUri,
            types=tuple(place.types),
        )

    async def _resolve_geography(
        self, session: aiohttp.ClientSession, geography: str
    ) -> GeographyScope:
        """Splits `geography` on commas and resolves each token — a known
        region/unrestricted term first (`domain.geography.resolve_known`),
        a live geocode for anything left — into one merged scope. Any
        unrestricted token makes the whole scope unrestricted: a buyer who
        lists `"GCC-wide, Global"` together is stating Global as an
        acceptable superset, so the union is genuinely unrestricted, not a
        case to work around. More than one resolved viewport collapses to
        none — `locationRestriction` takes a single rectangle, and
        `countries` (not the viewport) is what actually enforces
        correctness, so losing a tight box across several known geographies
        only widens the initial Places search, it never lets a wrong-country
        result through.
        """
        tokens = [t.strip() for t in geography.split(",") if t.strip()]
        if not tokens:
            return GeographyScope()

        countries: set[str] = set()
        viewports: list[Rectangle] = []
        for token in tokens:
            known = resolve_known(token)
            if known is not None:
                if known.unrestricted:
                    return GeographyScope(unrestricted=True)
                countries |= known.countries
                if known.viewport is not None:
                    viewports.append(known.viewport)
                continue

            viewport, country = await self._geocode(session, token)
            if country:
                countries.add(country)
            if viewport is not None:
                viewports.append(viewport)

        return GeographyScope(
            countries=frozenset(countries),
            viewport=viewports[0] if len(viewports) == 1 else None,
        )

    async def _geocode(
        self, session: aiohttp.ClientSession, token: str
    ) -> tuple[Rectangle | None, str | None]:
        if not token.strip():
            return None, None

        try:
            async with session.get(
                _GEOCODE_URL, params={"address": token, "key": self._api_key}
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "discovery_geocode_failed geography=%s status=%d",
                        token,
                        resp.status,
                    )
                    return None, None
                raw = await resp.json()
        except Exception as exc:
            # Not `exc_info=True`: the Geocoding API only supports the
            # `key` query param (no header-based auth like Places' own
            # `X-Goog-Api-Key`), and aiohttp's `ClientResponseError`/
            # `ContentTypeError` (e.g. a non-JSON error page for a bad or
            # rate-limited key) embeds the full request URL — including
            # that `key=` — in its own `str()`, which a traceback would log
            # verbatim. The exception type name is enough to debug from;
            # the key never should be.
            logger.warning(
                "discovery_geocode_error geography=%s error_type=%s",
                token,
                type(exc).__name__,
            )
            return None, None

        try:
            parsed = GeocodeResponse.model_validate(raw)
        except Exception:
            logger.warning("discovery_geocode_unparseable geography=%s", token)
            return None, None

        if parsed.status != "OK" or not parsed.results:
            # Expected, not an error: an unrecognized string legitimately
            # has no geocode result — the caller falls back to a
            # text-only search for this token.
            logger.info("discovery_geocode_no_result geography=%s status=%s", token, parsed.status)
            return None, None

        result = parsed.results[0]

        # `status: "OK"` only means Google matched *something* — not that
        # it's the kind of place a "geography" value means. A bare business
        # term (e.g. "GCC") can match an unrelated street address or
        # institution with high confidence and no error (verified live:
        # "GCC" -> "Glendale Community College", 1500 N Verdugo Rd —
        # `types` was `["book_store","establishment",...]`, not a
        # country/region at all). Reject anything outside
        # `_ACCEPTED_GEOCODE_TYPES`, and reject Google's own
        # `partial_match: true` ("didn't fully match the input").
        if result.partial_match or not (set(result.types) & _ACCEPTED_GEOCODE_TYPES):
            logger.info(
                "discovery_geocode_rejected geography=%s types=%s partial_match=%s",
                token,
                result.types,
                result.partial_match,
            )
            return None, None

        viewport: Rectangle | None = None
        if result.geometry and result.geometry.viewport:
            ne, sw = result.geometry.viewport.northeast, result.geometry.viewport.southwest
            if (
                ne is not None
                and sw is not None
                and ne.lat is not None
                and ne.lng is not None
                and sw.lat is not None
                and sw.lng is not None
            ):
                viewport = Rectangle(
                    low=LatLng(latitude=sw.lat, longitude=sw.lng),
                    high=LatLng(latitude=ne.lat, longitude=ne.lng),
                )

        country = next(
            (
                c.long_name
                for c in result.address_components
                if "country" in c.types and c.long_name
            ),
            None,
        )
        return viewport, country

    async def _search_places(
        self,
        session: aiohttp.ClientSession,
        *,
        text_query: str,
        location_restriction: Rectangle | None,
    ) -> list[Place] | None:
        request = PlacesSearchRequest(
            textQuery=text_query,
            pageSize=_PAGE_SIZE,
            locationRestriction=LocationRestriction(
                rectangle=LocationRestrictionRectangle(
                    low=PlaceLatLng(
                        latitude=location_restriction.low.latitude,
                        longitude=location_restriction.low.longitude,
                    ),
                    high=PlaceLatLng(
                        latitude=location_restriction.high.latitude,
                        longitude=location_restriction.high.longitude,
                    ),
                )
            )
            if location_restriction is not None
            else None,
        )
        body = request.model_dump(exclude_none=True)
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        }

        try:
            async with session.post(_SEARCH_URL, json=body, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(
                        "discovery_places_search_failed query=%s status=%d",
                        text_query,
                        resp.status,
                    )
                    return None
                raw = await resp.json()
        except Exception:
            logger.warning("discovery_places_search_error query=%s", text_query, exc_info=True)
            return None

        try:
            parsed = PlacesSearchResponse.model_validate(raw)
        except Exception:
            logger.warning("discovery_places_search_unparseable query=%s raw=%s", text_query, raw)
            return None

        return parsed.places
