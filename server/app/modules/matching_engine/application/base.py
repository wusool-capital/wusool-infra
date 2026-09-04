"""Shared constructor for every application-layer mixin in this module —
each mixin subclasses this instead of redeclaring its own `__init__`, so
`service.py`'s composed facade ends up with exactly one constructor no
matter how many mixins it combines.

Unlike `ddl_commands`' equivalent, this module's concerns don't share one
uniform dependency: `buyer_repository`/`meeting_repository` need a session
built by the caller (matching_engine's own `MatchingUnitOfWork` deliberately
doesn't expose a buyer repository — buyer data is read-only here, never
written through a transaction), while `run_match`/`approve_match`/etc. only
need `uow_factory`. One shared constructor means every composed
`MatchingEngineService` needs a `buyer_repository` in hand even when the
caller only wants `approve_match` — a real tradeoff of one facade over
several small, independently-constructed classes, accepted here for a
single composition point.

`extraction_service`/`reasoning_service` are collaborator objects, not
mixins — `application/requirements.py`'s `BuyerRequirementExtractionService`
and `matching/reasoning_service.py`'s `MatchReasoningService` stay their own
standalone classes since nothing outside `MatchingMixin.run_match` ever
calls them directly (see `bootstrap.py` for how they're assembled).
"""

from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningService,
)
from app.modules.matching_engine.application.ports.buyers import BuyerRepositoryPort
from app.modules.matching_engine.application.ports.matching import CandidateRetriever
from app.modules.matching_engine.application.ports.meetings import MeetingRepositoryPort
from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.ports.web_search import FirecrawlClient
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
)
from app.modules.matching_engine.domain.matching.scoring import ScoringEngine


class ServiceBase:
    def __init__(
        self,
        uow_factory: MatchingUnitOfWorkFactory,
        *,
        buyer_repository: BuyerRepositoryPort,
        extraction_service: BuyerRequirementExtractionService,
        reasoning_service: MatchReasoningService,
        candidate_retriever: CandidateRetriever,
        scoring_engine: ScoringEngine,
        top_n: int,
        meeting_repository: MeetingRepositoryPort | None = None,
        enable_seller_meeting_notes: bool = False,
        firecrawl_client: FirecrawlClient | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._buyers = buyer_repository
        self._meetings = meeting_repository
        self._extraction_service = extraction_service
        self._reasoning_service = reasoning_service
        self._candidate_retriever = candidate_retriever
        self._scoring_engine = scoring_engine
        self._top_n = top_n
        self._enable_seller_meeting_notes = enable_seller_meeting_notes
        self._firecrawl_client = firecrawl_client
