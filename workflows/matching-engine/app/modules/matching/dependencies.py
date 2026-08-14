"""Composition root for the matching pipeline's use cases — wires config and
infrastructure together. Slack handlers call these factories; they never
construct services/repositories themselves (§2, §36).
"""

from functools import lru_cache

from app.config import get_settings
from app.modules.llm.domain.bedrock_client import InferenceConfig
from app.modules.llm.infrastructure.bedrock_converse_client import BedrockConverseClient
from app.modules.matching.application.reasoning_service import MatchReasoningService
from app.modules.matching.application.use_cases import (
    GetMatchAnalysisUseCase,
    GetMatchRunViewUseCase,
    RunBuyerSellerMatchUseCase,
)
from app.modules.matching.domain.scoring import ScoringEngine
from app.modules.matching.infrastructure.structured_candidate_retriever import (
    StructuredCandidateRetriever,
)
from app.modules.requirements.application.extraction_service import (
    BuyerRequirementExtractionService,
)
from app.modules.web_search.application.lead_search_service import WebLeadSearchService
from app.modules.web_search.infrastructure.firecrawl_maps_client import FirecrawlMapsClient
from app.shared.database import get_sessionmaker


def _inference_config() -> InferenceConfig:
    settings = get_settings()
    return InferenceConfig(
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        top_p=settings.llm_top_p,
    )


@lru_cache
def _bedrock_client() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_run_match_use_case() -> RunBuyerSellerMatchUseCase:
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    bedrock = _bedrock_client()
    inference_config = _inference_config()

    return RunBuyerSellerMatchUseCase(
        sessionmaker,
        extraction_service=BuyerRequirementExtractionService(
            bedrock,
            model_id=settings.aws_bedrock_model_id_extraction,
            inference_config=inference_config,
        ),
        candidate_retriever=StructuredCandidateRetriever(sessionmaker),
        scoring_engine=ScoringEngine(
            {
                "llm_extracted": settings.confidence.llm_extracted,
                "llm_inferred": settings.confidence.llm_inferred,
            }
        ),
        reasoning_service=MatchReasoningService(
            bedrock,
            model_id=settings.aws_bedrock_model_id_reasoning,
            inference_config=inference_config,
        ),
        top_n=settings.stage3_top_n,
    )


def build_match_analysis_use_case() -> GetMatchAnalysisUseCase:
    return GetMatchAnalysisUseCase(get_sessionmaker())


def build_match_run_view_use_case() -> GetMatchRunViewUseCase:
    return GetMatchRunViewUseCase(get_sessionmaker())


@lru_cache
def _firecrawl_client() -> FirecrawlMapsClient | None:
    api_key = get_settings().firecrawl_api_key
    return FirecrawlMapsClient(api_key) if api_key else None


def build_web_lead_search_service() -> WebLeadSearchService | None:
    """Returns `None` when no `FIRECRAWL_API_KEY` is configured — the caller
    must treat that the same as "no leads found" and fall back to the plain
    no-candidates message, not crash."""
    client = _firecrawl_client()
    return WebLeadSearchService(get_sessionmaker(), client) if client else None
