"""Compose ddl_commands application use cases behind one module facade.

Attio webhook dispatch (`application/attio_sync.py`) stays outside this
facade: `dispatch_event` is a stateless per-event dispatcher called with a
fresh `AttioSyncRepositoryPort`/`AttioRegistryPort`/`AttioClientProtocol`
each webhook delivery (see `api/attio_sync.py`), not a service with
dependencies injected once the way `ServiceBase`'s `uow_factory` is here —
forcing it into this class would need a constructor shape it doesn't
actually have.
"""

from app.modules.ddl_commands.application.buyers import BuyerService
from app.modules.ddl_commands.application.sellers import SellerService


class DdlCommandsService(BuyerService, SellerService):
    """No business logic of its own — combines every concern mixin above
    into one composed class. Add a new use-case area as its own
    `ServiceBase` mixin and list it here, rather than growing this class or
    a mixin file directly.
    """
