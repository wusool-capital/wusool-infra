"""Composition roots for Slack handlers.

`_seller_draft_port_holder` is registered once at process startup by
`server/main.py` via `configure_seller_draft_port` — `discovery` never
imports `ddl_commands`, so it cannot build its own adapter; see
`discovery/__init__.py`'s docstring. `_seller_writer_port_holder` follows
the same pattern via `configure_seller_writer_port`.
"""

import json
import logging
from dataclasses import asdict
from functools import lru_cache

from app.modules.discovery.application.base import CreationPolicy
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.ports.seller_writer import SellerWriterPort
from app.modules.discovery.application.service import DiscoveryService
from app.modules.discovery.bootstrap import build_discovery_service, build_lead_search_client
from app.modules.discovery.config import get_settings
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.providers.google_places.client import GooglePlacesClient
from app.modules.utilities import FixedWindowRateLimiter, NotFoundError, get_shared_ephemeral_store

logger = logging.getLogger(__name__)

_seller_draft_port_holder: SellerDraftPort | None = None


def configure_seller_draft_port(port: SellerDraftPort) -> None:
    global _seller_draft_port_holder
    _seller_draft_port_holder = port


def _seller_draft_port() -> SellerDraftPort:
    if _seller_draft_port_holder is None:
        raise RuntimeError(
            "discovery seller-draft port not configured — call configure_seller_draft_port() "
            "at startup"
        )
    return _seller_draft_port_holder


_seller_writer_port_holder: SellerWriterPort | None = None

_ONE_DAY_S = 24 * 60 * 60


def configure_seller_writer_port(port: SellerWriterPort) -> None:
    global _seller_writer_port_holder
    _seller_writer_port_holder = port


def _seller_writer_port() -> SellerWriterPort:
    if _seller_writer_port_holder is None:
        raise RuntimeError(
            "discovery seller-writer port not configured — call configure_seller_writer_port() "
            "at startup"
        )
    return _seller_writer_port_holder


@lru_cache
def _search_limiter() -> FixedWindowRateLimiter:
    # In-process: resets on deploy and isn't shared across instances, which
    # is enough for a guard against a runaway loop.
    return FixedWindowRateLimiter(
        limit=get_settings().discovery_daily_search_cap, window_s=_ONE_DAY_S
    )


def _creation_policy() -> CreationPolicy:
    settings = get_settings()
    return CreationPolicy(
        lead_limit=settings.discovery_lead_search_limit,
        enrichment_concurrency=settings.discovery_enrichment_concurrency,
        enrichment_budget_s=settings.discovery_enrichment_budget_s,
    )


@lru_cache
def _lead_search_client() -> GooglePlacesClient | None:
    api_key = get_settings().google_places_api_key
    if not api_key:
        logger.warning(
            "google_places_api_key_unset — seller discovery is disabled; "
            "set GOOGLE_PLACES_API_KEY to enable it"
        )
        return None
    return build_lead_search_client(api_key)


def discovery_service() -> DiscoveryService:
    return build_discovery_service(
        lead_search_client=_lead_search_client(),
        seller_draft_port=_seller_draft_port(),
        seller_writer_port=_seller_writer_port(),
        search_limiter=_search_limiter(),
        policy=_creation_policy(),
    )


def encode_lead(lead: DiscoveredLead) -> str:
    """Serializes a lead and stores it server-side, returning a short token
    for the "Add as seller" button's `value` — `DiscoveredLead`'s fields
    are fixed (never grows the way `enrichment`'s proposed-field list did),
    but an unusually long `name`/`address` from a Places result is still
    real data, not something to truncate, so this goes through the same
    `utilities.get_shared_ephemeral_store` token indirection as
    `enrichment`'s proposal and `ddl_commands`' organization-selection
    payload rather than trusting the button value to always stay small.
    `asdict` instead of a hand-written literal keeps the stored JSON in
    sync with `DiscoveredLead`'s actual fields by construction — a field
    added there without a matching update here was the exact class of bug
    this replaces.
    """
    return get_shared_ephemeral_store().put(json.dumps(asdict(lead)))


def decode_lead(token: str) -> DiscoveredLead:
    """Raises `NotFoundError` for an expired/unknown token — the caller
    (`handlers.handle_discover_add_seller`) already treats any decode
    failure as "couldn't process that lead," so no new handling is needed
    there. `types` is rebuilt as a tuple — JSON has no tuple type, so it
    round-trips through the store as a list, which would otherwise never
    compare equal to the frozen dataclass's own tuple field.
    """
    payload = get_shared_ephemeral_store().get(token)
    if payload is None:
        raise NotFoundError(f"No stored lead for token {token!r}")
    fields = json.loads(payload)
    fields["types"] = tuple(fields.get("types", ()))
    return DiscoveredLead(**fields)
