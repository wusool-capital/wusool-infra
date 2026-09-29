"""Shared constructor for every application-layer mixin in this module."""

from dataclasses import dataclass

from app.modules.discovery.application.ports.research import LeadSearchClient
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.ports.seller_writer import SellerWriterPort
from app.modules.utilities import FixedWindowRateLimiter


@dataclass(frozen=True)
class CreationPolicy:
    lead_limit: int
    enrichment_concurrency: int
    enrichment_budget_s: float


class ServiceBase:
    def __init__(
        self,
        *,
        lead_search_client: LeadSearchClient | None,
        seller_draft_port: SellerDraftPort,
        seller_writer_port: SellerWriterPort,
        search_limiter: FixedWindowRateLimiter,
        policy: CreationPolicy,
    ) -> None:
        self._lead_search_client = lead_search_client
        self._seller_draft_port = seller_draft_port
        self._seller_writer_port = seller_writer_port
        self._search_limiter = search_limiter
        self._policy = policy
