"""Implements `application.ports.attio_sync.AttioRegistryPort` by delegating
to `app.modules.attio.providers.attio.registry`'s free functions — this
module's own thin adapter over the cross-module `attio` module's
object/list-slug lookup, so `application/` never imports that module's
`providers/` directly.
"""

from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio import registry


class AttioRegistry:
    async def object_slug(self, client: AttioClientProtocol, object_id: str) -> str | None:
        return await registry.object_slug(client, object_id)

    async def list_slug(self, client: AttioClientProtocol, list_id: str) -> str | None:
        return await registry.list_slug(client, list_id)
