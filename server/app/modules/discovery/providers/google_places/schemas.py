"""Locally-scoped Pydantic models parsing Google's Places API (New) Text
Search and Geocoding API responses — never exported as this module's public
schema.

Written against Google's published reference
(https://developers.google.com/maps/documentation/places/web-service/text-search,
https://developers.google.com/maps/documentation/geocoding/requests-geocoding),
not yet verified against a live account. Every field is optional with a
default, same convention as `enrichment.providers.diffbot.schemas` — a
missing field here should degrade the mapping, not raise.

Casing gotcha: the two APIs disagree. Places (New) is camelCase
(`addressComponents`, `longText`); the (older) Geocoding API is snake_case
(`address_components`, `long_name`). Both are kept verbatim rather than
normalized to one style, matching every other provider schema in this repo.
"""

from pydantic import BaseModel

# --- Places Text Search (New) --------------------------------------------


class LocalizedText(BaseModel):
    text: str | None = None


class PlaceAddressComponent(BaseModel):
    longText: str | None = None
    types: list[str] = []


class Place(BaseModel):
    displayName: LocalizedText | None = None
    formattedAddress: str | None = None
    googleMapsUri: str | None = None
    primaryTypeDisplayName: LocalizedText | None = None
    websiteUri: str | None = None
    addressComponents: list[PlaceAddressComponent] = []
    types: list[str] = []


class PlacesSearchResponse(BaseModel):
    places: list[Place] = []


# --- Geocoding API ----------------------------------------------------------


class GeocodeLatLng(BaseModel):
    lat: float | None = None
    lng: float | None = None


class GeocodeViewport(BaseModel):
    northeast: GeocodeLatLng | None = None
    southwest: GeocodeLatLng | None = None


class GeocodeAddressComponent(BaseModel):
    long_name: str | None = None
    types: list[str] = []


class GeocodeGeometry(BaseModel):
    viewport: GeocodeViewport | None = None


class GeocodeResult(BaseModel):
    geometry: GeocodeGeometry | None = None
    address_components: list[GeocodeAddressComponent] = []
    # Both feed the false-match guard in `client.py::_geocode` — a bare
    # business/CRM term (e.g. "GCC") can match an unrelated street address
    # or institution with `status: OK` and no error; `types` distinguishes
    # a real country/region match from a business/POI one, and
    # `partial_match` is Google's own "didn't fully match the input" flag.
    types: list[str] = []
    partial_match: bool = False


class GeocodeResponse(BaseModel):
    status: str = ""
    results: list[GeocodeResult] = []


# --- Places `searchText` request body ---------------------------------------
# Built by `client.py`, not parsed from a response — fields are required
# rather than optional-with-default, unlike every model above. `.model_dump`
# is what actually reaches `aiohttp`'s `json=` kwarg.


class PlaceLatLng(BaseModel):
    latitude: float
    longitude: float


class LocationRestrictionRectangle(BaseModel):
    low: PlaceLatLng
    high: PlaceLatLng


class LocationRestriction(BaseModel):
    rectangle: LocationRestrictionRectangle


class PlacesSearchRequest(BaseModel):
    textQuery: str
    pageSize: int
    locationRestriction: LocationRestriction | None = None
