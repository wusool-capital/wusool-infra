"""Attio CRM vendor integration — the generic API client, value-extraction
helpers, and webhook envelope shape. `ddl_commands` is this module's one
real consumer today; extracted into its own peer module for organizational
clarity (Attio is a large, self-contained ~30-file integration surface),
not because a second consumer exists yet — same one-directional-dependency
shape as `notifications`/`organizations`.

Like `utilities`, treated as a full-access peer module rather than being
forced through a narrow Port surface: `ddl_commands` imports directly from
`app.modules.attio.providers.attio.*`/`app.modules.attio.domain.*` for the
specific helpers it needs (date/money serialization, signature
verification, retry, registry lookups), not just `AttioClientProtocol`.
"""

from app.modules.attio.application.ports.client import AttioClientProtocol
from app.modules.attio.domain.webhook import WebhookEvent, WebhookEventId
from app.modules.attio.providers.attio.client import AttioClient, AttioError, get_attio_client

__all__ = [
    "AttioClient",
    "AttioClientProtocol",
    "AttioError",
    "WebhookEvent",
    "WebhookEventId",
    "get_attio_client",
]
