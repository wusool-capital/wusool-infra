"""The one entry point another module calls to trigger enrichment for a
buyer/seller it already has a role id for — `matching_engine`'s "enrich
this buyer/seller" buttons use this rather than resolving org info
themselves. Exported via this module's root `__all__`.
"""

import logging
import uuid

from app.modules.enrichment.api.dependencies import (
    enrichment_service,
    propose_and_post,
    resolve_target,
)
from app.modules.enrichment.domain.proposals import BasicEnrichment
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


async def enrich_and_post(*, kind: str, role_id: str, channel_id: str) -> None:
    target = await resolve_target(kind=kind, role_id=uuid.UUID(role_id))
    if target is None:
        logger.warning("enrich_and_post_target_not_found", extra={"kind": kind, "role_id": role_id})
        return
    await propose_and_post(target, channel_id=channel_id)


async def propose_basic_seller_fields(
    *, org_name: str, domain: str | None, current_values: JsonObject
) -> BasicEnrichment:
    """Basic-tier (structured providers only) seller enrichment for a company
    that isn't saved yet — used by discovery to fill a lead before its one
    Attio-first write. Never writes anything."""
    return await enrichment_service().propose_basic(
        org_name=org_name, domain=domain, current_values=current_values
    )
