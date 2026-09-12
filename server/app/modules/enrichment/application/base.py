"""Shared constructor for every application-layer mixin in this module —
each mixin subclasses this instead of redeclaring its own `__init__`, so
`service.py`'s composed facade ends up with exactly one constructor no
matter how many mixins it combines. Mirrors `matching_engine`'s own
`application/base.py`.
"""

from app.modules.enrichment.application.ports.company_data import CompanyDataClient
from app.modules.enrichment.application.ports.llm import ExtractionClient
from app.modules.enrichment.application.ports.research import ResearchClient
from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.ports.role_reader import RoleReaderPort


class ServiceBase:
    def __init__(
        self,
        *,
        research_client: ResearchClient | None,
        extraction_client: ExtractionClient,
        role_reader: RoleReaderPort,
        review_port: EnrichmentReviewPort,
        model_id: str,
        temperature: float,
        max_tokens: int,
        min_confidence: float,
        company_data_clients: tuple[CompanyDataClient, ...] = (),
    ) -> None:
        self._research_client = research_client
        self._extraction_client = extraction_client
        self._role_reader = role_reader
        self._review_port = review_port
        self._model_id = model_id
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._min_confidence = min_confidence
        # Structured company-data tier of the seller research waterfall
        # (Diffbot, then People Data Labs) — tried in order, before the
        # free-text `ResearchClient` + LLM extraction path. Empty for
        # buyer targets: see `EnrichMixin.propose`.
        self._company_data_clients = company_data_clients
