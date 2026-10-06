"""Composed facade — no business logic of its own."""

from app.modules.discovery.application.confirm import ConfirmMixin
from app.modules.discovery.application.create import CreateMixin
from app.modules.discovery.application.discover import DiscoverMixin


class DiscoveryService(DiscoverMixin, CreateMixin, ConfirmMixin):
    pass
