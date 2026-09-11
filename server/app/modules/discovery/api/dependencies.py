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
    """Serializes a lead into a Slack button `value` — small enough (well
    under Slack's 2000-char button-value limit) to round-trip through a
    single button click rather than a server-side stash. `asdict` instead
    of a hand-written literal keeps this in sync with `DiscoveredLead`'s
    actual fields by construction — a field added there without a matching
    update here was the exact class of bug this replaces.
    """
    return json.dumps(asdict(lead))


def decode_lead(value: str) -> DiscoveredLead:
    return DiscoveredLead(**json.loads(value))
