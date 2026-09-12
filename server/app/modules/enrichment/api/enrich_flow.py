"""The one entry point another module calls to trigger enrichment for a
buyer/seller it already has a role id for — `matching_engine`'s "enrich
this buyer/seller" buttons use this rather than resolving org info
themselves. Exported via this module's root `__all__`.
"""

import logging
import uuid

from app.modules.enrichment.api.dependencies import propose_and_post, resolve_target

logger = logging.getLogger(__name__)


async def enrich_and_post(*, kind: str, role_id: str, channel_id: str) -> None:
    target = await resolve_target(kind=kind, role_id=uuid.UUID(role_id))
    if target is None:
        logger.warning("enrich_and_post_target_not_found", extra={"kind": kind, "role_id": role_id})
        return
    await propose_and_post(target, channel_id=channel_id)
