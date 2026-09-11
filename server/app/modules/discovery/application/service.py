"""Composed facade — no business logic of its own."""

from app.modules.discovery.application.confirm import ConfirmMixin
from app.modules.discovery.application.discover import DiscoverMixin


class DiscoveryService(DiscoverMixin, ConfirmMixin):
    pass
