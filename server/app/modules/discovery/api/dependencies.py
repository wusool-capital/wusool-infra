"""Composition roots for Slack handlers.

`_seller_draft_port_holder` is registered once at process startup by
`server/main.py` via `configure_seller_draft_port` — `discovery` never
imports `ddl_commands`, so it cannot build its own adapter; see
`discovery/__init__.py`'s docstring.
"""

import json
import logging
from dataclasses import asdict
from functools import lru_cache

from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.service import DiscoveryService
from app.modules.discovery.bootstrap import build_discovery_service, build_lead_search_client
from app.modules.discovery.config import get_settings
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.providers.firecrawl.client import FirecrawlMapsClient
from app.modules.utilities import NotFoundError, get_shared_ephemeral_store

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


@lru_cache
def _lead_search_client() -> FirecrawlMapsClient | None:
    api_key = get_settings().firecrawl_api_key
    if not api_key:
        logger.warning(
            "firecrawl_api_key_unset — seller discovery is disabled; "
            "set FIRECRAWL_API_KEY to enable it"
        )
        return None
    return build_lead_search_client(api_key)


def discovery_service() -> DiscoveryService:
    return build_discovery_service(
        lead_search_client=_lead_search_client(), seller_draft_port=_seller_draft_port()
    )


def encode_lead(lead: DiscoveredLead) -> str:
    """Serializes a lead and stores it server-side, returning a short token
    for the "Add as seller" button's `value` — `DiscoveredLead`'s 4 fields
    are fixed (never grows the way `enrichment`'s proposed-field list did),
    but an unusually long `name`/`address` from a Maps result is still real
    data, not something to truncate, so this goes through the same
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
    there.
    """
    payload = get_shared_ephemeral_store().get(token)
    if payload is None:
        raise NotFoundError(f"No stored lead for token {token!r}")
    return DiscoveredLead(**json.loads(payload))
