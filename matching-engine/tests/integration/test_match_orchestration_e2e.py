"""§33 deterministic end-to-end test: buyer -> mocked extraction -> real
Stage 1 filtering -> real Stage 2 scoring -> mocked reasoning -> persistence
-> result DTO. No Slack. Requires a real (rolled-back) database transaction —
skips cleanly if unreachable, same as the rest of `tests/integration/`.

Candidate loading itself is faked (a real `StructuredCandidateRetriever`
would hit the live, unpredictable ~172-row `seller_roles` table) so the
shortlist is deterministic — built from one real `seller_roles` fixture row
so persistence's FK to `seller_roles.id` is still genuine. The real
`apply_structured_filters` still runs against it.
"""

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.buyers.application.mappers import to_buyer_context
from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.llm.domain.bedrock_client import InferenceConfig
from app.modules.matching.application.reasoning_service import MatchReasoningService
from app.modules.matching.application.use_cases import RunBuyerSellerMatchUseCase
from app.modules.matching.domain.candidate_retriever import CandidateBatch
from app.modules.matching.domain.scoring import ScoringEngine, apply_structured_filters
from app.modules.matching.infrastructure.repositories import MatchResultRepository
from app.modules.requirements.application.extraction_service import (
    BuyerRequirementExtractionService,
)
from app.modules.sellers.application.mappers import to_seller_candidate
from app.modules.sellers.infrastructure.models import SellerRole
from tests.fakes.bedrock import FakeBedrockClient

EXTRACTION_RESPONSE = {
    "hard_requirements": [],
    "soft_preferences": [],
    "strategic_thesis": "Deterministic e2e test thesis",
    "ideal_target_description": "Any profitable target",
    "scoring_rubric": {},
    "data_confidence": 0.5,
}


class _FixtureCandidateRetriever:
    """A `CandidateRetriever` over one known, real seller — runs the real
    Stage 1 filter against it rather than hitting the live `seller_roles`
    table, so the shortlist is deterministic.
    """

    def __init__(self, candidates: list) -> None:
        self._candidates = candidates

    async def get_candidates(self, buyer, profile):  # noqa: ANN001
        passed, filters_skipped = apply_structured_filters(profile, self._candidates)
        return CandidateBatch(
            passed=passed, filters_skipped=filters_skipped, considered=len(self._candidates)
        )


def _inference_config() -> InferenceConfig:
    return InferenceConfig(temperature=0.2, max_tokens=4096, top_p=0.9)


async def test_deterministic_match_run_end_to_end(
    db_sessionmaker: async_sessionmaker,
    any_buyer_role: BuyerRole,
    any_seller_role: SellerRole,
) -> None:
    async with db_sessionmaker() as session:
        await session.refresh(any_buyer_role, attribute_names=["organization"])
        await session.refresh(any_seller_role, attribute_names=["organization"])
        buyer = to_buyer_context(any_buyer_role)
        seller_candidate = to_seller_candidate(any_seller_role)

    reasoning_response = {
        "candidates": [
            {
                "seller_role_id": seller_candidate.seller_role_id,
                "why_it_matches": "Matches on the (empty) requirement set.",
                "why_chosen_over_alternatives": "Only candidate in this deterministic test.",
                "recommended_pitch": "Position as a strong strategic fit.",
                "risks_and_gaps": "No hard requirements were extracted to verify.",
                "confidence_narrative": "Low confidence — minimal buyer data available.",
            }
        ]
    }

    extraction_service = BuyerRequirementExtractionService(
        FakeBedrockClient(structured_responses=[EXTRACTION_RESPONSE]),
        model_id="test-extraction-model",
        inference_config=_inference_config(),
    )
    reasoning_service = MatchReasoningService(
        FakeBedrockClient(reasoning_responses=[reasoning_response]),
        model_id="test-reasoning-model",
        inference_config=_inference_config(),
    )
    use_case = RunBuyerSellerMatchUseCase(
        db_sessionmaker,
        extraction_service=extraction_service,
        candidate_retriever=_FixtureCandidateRetriever([seller_candidate]),
        scoring_engine=ScoringEngine({"llm_extracted": 0.6, "llm_inferred": 0.4}),
        reasoning_service=reasoning_service,
        top_n=3,
    )

    result = await use_case.execute(buyer, requested_by="U_TEST_SLACK_USER")

    assert result.status == "GENERATED"
    assert len(result.results) == 1
    shortlisted = result.results[0]
    assert shortlisted.seller_role_id == seller_candidate.seller_role_id
    assert shortlisted.rank == 1
    assert shortlisted.why_it_matches == "Matches on the (empty) requirement set."

    # Persisted state is actually recoverable, not just returned in the DTO.
    async with db_sessionmaker() as session:
        repo = MatchResultRepository(session)

        run = await repo.get_run(uuid.UUID(result.run_id))
        assert run is not None
        assert run.status == "GENERATED"
        assert run.requirement_profile_version == 1
        assert run.candidates_considered == 1

        candidates = await repo.get_candidates(uuid.UUID(result.run_id))
        assert len(candidates) == 1
        assert candidates[0].match_score_id is not None

        scores = await repo.get_scores_for_run(uuid.UUID(result.run_id))
        assert len(scores) == 1
