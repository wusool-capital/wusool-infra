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

from app.models import BuyerRole, SellerRole
from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningService,
)
from app.modules.matching_engine.application.matching.use_cases import (
    RunBuyerSellerMatchUseCase,
)
from app.modules.matching_engine.application.ports.llm import InferenceConfig
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
)
from app.modules.matching_engine.domain.matching.entities import CandidateBatch
from app.modules.matching_engine.domain.matching.scoring import (
    ScoringEngine,
    apply_structured_filters,
)
from app.modules.matching_engine.persistence.repositories.buyers_repository import BuyerRepository
from app.modules.matching_engine.persistence.repositories.matching_repository import (
    MatchResultRepository,
)
from app.modules.matching_engine.persistence.repositories.sellers_repository import SellerRepository
from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork
from app.modules.matching_engine.tests.fakes.bedrock import FakeBedrockClient

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
    # `any_buyer_role`/`any_seller_role` are bound to the `db_session` fixture's
    # own session, not this use case's `db_sessionmaker` — re-fetch fresh
    # copies in a session from `db_sessionmaker` instead of refreshing
    # instances across sessions (each session has its own identity map).
    async with db_sessionmaker() as session:
        buyer_repo = BuyerRepository(session)
        seller_repo = SellerRepository(session)
        buyer = await buyer_repo.get_with_organization(str(any_buyer_role.id))
        seller_candidate = await seller_repo.get_with_organization(str(any_seller_role.id))
        assert buyer is not None
        assert seller_candidate is not None

        # Don't assume this buyer has never had a run before — a real
        # /find-match invocation against this same database (manual testing,
        # or a prior test run) may have already assigned versions.
        match_repo = MatchResultRepository(session)
        previous_version = await match_repo.get_latest_requirement_profile_version(
            uuid.UUID(buyer.buyer_role_id)
        )
    expected_next_version = (previous_version or 0) + 1

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
        lambda: SqlAlchemyMatchingUnitOfWork(db_sessionmaker),
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
        assert run.requirement_profile_version == expected_next_version
        assert run.candidates_considered == 1

        candidates = await repo.get_candidates(uuid.UUID(result.run_id))
        assert len(candidates) == 1
        assert candidates[0].match_score_id is not None

        scores = await repo.get_scores_for_run(uuid.UUID(result.run_id))
        assert len(scores) == 1
