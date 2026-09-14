"""Real Google Places implementation of `LeadSearchClient`. Replaces
`FirecrawlMapsClient` — same `discovery`-owns-lead-search rationale, now
against Google's typed Places API (New) + Geocoding API instead of scraping
a Google Maps search page.

Two calls per `find_potential_sellers`, sharing one `aiohttp.ClientSession`:
`_geocode` resolves `geography` to a viewport (for `locationRestriction`) and
a country (for a hard post-filter — see module docstring on
`find_potential_sellers` for why the viewport alone isn't a real guarantee),
then `_search_places` runs the actual text search — `geography` always stays
in the query text too, restricted or not, since `locationRestriction` narrows
a categorical search rather than replacing the text hint entirely. A
`geography` that fails to geocode (empty string, or anything but
`status: "OK"`) falls back to an unrestricted, unfiltered search — the same
unbounded behavior the old Firecrawl scrape always had.
"""

import logging
from urllib.parse import quote

import aiohttp

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
            viewport, country = await self._geocode(session, geography)
            places = await self._search_places(
                session, text_query=text_query, location_restriction=viewport
            )
        if places is None:
            return []

        if country:
            kept: list[Place] = []
            dropped = 0
            unverified = 0
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
                elif place_country == country:
                    kept.append(p)
                else:
                    dropped += 1
            if dropped:
                logger.info(
                    "discovery_leads_out_of_country query=%s expected_country=%s dropped=%d",
                    text_query,
                    country,
                    dropped,
                )
            if unverified:
                logger.info(
                    "discovery_leads_unverified_country query=%s expected_country=%s "
                    "kept_without_verification=%d",
                    text_query,
                    country,
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

    async def _geocode(
        self, session: aiohttp.ClientSession, geography: str
    ) -> tuple[LocationRestrictionRectangle | None, str | None]:
        if not geography.strip():
            return None, None

        try:
            async with session.get(
                _GEOCODE_URL, params={"address": geography, "key": self._api_key}
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "discovery_geocode_failed geography=%s status=%d",
                        geography,
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
                geography,
                type(exc).__name__,
            )
            return None, None

        try:
            parsed = GeocodeResponse.model_validate(raw)
        except Exception:
            logger.warning("discovery_geocode_unparseable geography=%s", geography)
            return None, None

        if parsed.status != "OK" or not parsed.results:
            # Expected, not an error: a region-shaped `geography` (e.g.
            # "MENA") or an unrecognized string legitimately has no single
            # geocode result — the caller falls back to a text-only search.
            logger.info(
                "discovery_geocode_no_result geography=%s status=%s", geography, parsed.status
            )
            return None, None

        result = parsed.results[0]
        viewport: LocationRestrictionRectangle | None = None
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
                viewport = LocationRestrictionRectangle(
                    low=PlaceLatLng(latitude=sw.lat, longitude=sw.lng),
                    high=PlaceLatLng(latitude=ne.lat, longitude=ne.lng),
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
        location_restriction: LocationRestrictionRectangle | None,
    ) -> list[Place] | None:
        request = PlacesSearchRequest(
            textQuery=text_query,
            pageSize=_PAGE_SIZE,
            locationRestriction=LocationRestriction(rectangle=location_restriction)
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
