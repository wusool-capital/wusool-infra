"""Composed facade — no business logic of its own, combines every concern
mixin above so callers construct one object regardless of how many
concerns this module has.
"""

from app.modules.enrichment.application.enrich import EnrichMixin
from app.modules.enrichment.application.review import ReviewMixin


class EnrichmentService(EnrichMixin, ReviewMixin):
    pass
