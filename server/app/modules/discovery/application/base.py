"""Shared constructor for every application-layer mixin in this module."""

from app.modules.discovery.application.ports.research import LeadSearchClient
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort


class ServiceBase:
    def __init__(
        self,
        *,
        lead_search_client: LeadSearchClient | None,
        seller_draft_port: SellerDraftPort,
    ) -> None:
        self._lead_search_client = lead_search_client
        self._seller_draft_port = seller_draft_port
