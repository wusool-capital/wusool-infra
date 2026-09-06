"""Stage 3 (§15-16). The Bedrock reasoning call receives the buyer's
requirement profile, the shortlisted sellers, and their deterministic
criterion scores/evidence — it is responsible for qualitative narrative
only: why a match works, why it was chosen over the alternatives, a
recommended pitch, and risks/gaps. It is never responsible for the numeric
score, hard-filter decisions, entity IDs, or database writes.

The Bedrock Port owns the validate-repair-retry-then-fail-closed policy
(`application/ports/llm.py`) — this service only builds the prompt/repair
prompt (business-content-aware) and converts the already-validated result
dict into the domain `ReasoningOutcome`. No `pydantic` import here: the
vendor-response schema (`providers/bedrock/schemas.py`) never crosses this
boundary.
"""

from dataclasses import asdict

from app.modules.matching_engine.application.errors import MatchReasoningError
from app.modules.matching_engine.application.ports.llm import (
    BedrockClient,
    InferenceConfig,
)
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import (
    CandidateNarrative,
    CandidateScore,
    ReasoningOutcome,
)
from app.modules.matching_engine.domain.meetings import render_meeting_notes_section
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError


class MatchReasoningService:
    def __init__(
        self,
        bedrock_client: BedrockClient,
        *,
        model_id: str,
        inference_config: InferenceConfig,
        meeting_notes_char_budget: int = 4000,
    ) -> None:
        self._client = bedrock_client
        self._model_id = model_id
        self._inference_config = inference_config
        self._meeting_notes_char_budget = meeting_notes_char_budget

    async def reason(
        self,
        buyer: BuyerContext,
        profile: RequirementProfile,
        shortlist: list[tuple[SellerCandidate, CandidateScore]],
    ) -> ReasoningOutcome:
        try:
            result = await self._client.generate_reasoning(
                model_id=self._model_id,
                prompt=self._build_prompt(buyer, profile, shortlist),
                repair_prompt_builder=lambda invalid_raw, error: self._build_repair_prompt(
                    buyer, profile, shortlist, invalid_raw, error
                ),
                inference_config=self._inference_config,
            )
        except BedrockInvocationError as exc:
            raise MatchReasoningError(
                f"Bedrock reasoning output for buyer_role={buyer.buyer_role_id} failed "
                "validation after one repair attempt"
            ) from exc

        return ReasoningOutcome(candidates=[CandidateNarrative(**c) for c in result["candidates"]])

    def _build_prompt(
        self,
        buyer: BuyerContext,
        profile: RequirementProfile,
        shortlist: list[tuple[SellerCandidate, CandidateScore]],
    ) -> str:
        candidates_context = [
            {
                "seller_role_id": seller.seller_role_id,
                "org_name": seller.org_name,
                "outreach_tier": seller.outreach_tier,
                "relationship_status": seller.relationship_status,
                "est_revenue": asdict(seller.est_revenue) if seller.est_revenue else None,
                "est_ebitda": asdict(seller.est_ebitda) if seller.est_ebitda else None,
                "geographic_focus": seller.geographic_focus,
                "sector_focus": seller.sector_focus,
                "overall_score": score.overall_score,
                "data_confidence": score.confidence.value,
                "criteria": [
                    {
                        "criterion": c.criterion,
                        "type": c.criterion_type,
                        "result": c.result,
                        "data_backing": c.data_backing,
                    }
                    for c in score.criteria
                ],
                "meeting_notes": render_meeting_notes_section(
                    seller.meeting_notes,
                    total_char_budget=self._meeting_notes_char_budget,
                    subject_name=seller.org_name,
                )
                or None,
            }
            for seller, score in shortlist
        ]
        meeting_notes_section = render_meeting_notes_section(
            buyer.meeting_notes,
            total_char_budget=self._meeting_notes_char_budget,
            subject_name=buyer.org_name,
        )
        buyer_meeting_notes_line = f"\n{meeting_notes_section}" if meeting_notes_section else ""
        return (
            "Explain, per candidate, why each shortlisted seller matches this "
            "buyer, why it ranks where it does relative to the others, a "
            "recommended pitch, and any risks/gaps — grounded only in the data "
            "given below, never in documents or facts you were not given. "
            "Return strict JSON: {candidates: [{seller_role_id, why_it_matches, "
            "why_chosen_over_alternatives, recommended_pitch, risks_and_gaps, "
            "confidence_narrative}]}. You are not responsible for the numeric "
            "score, hard-filter decisions, or database writes — those are "
            "already decided; only explain them. Return only the JSON object "
            "itself — no markdown code fences, no explanation before or after "
            "it.\n\n"
            f"Buyer: {buyer.org_name}\n"
            f"Strategic thesis: {profile.strategic_thesis or 'Unknown'}\n"
            f"Ideal target: {profile.ideal_target_description or 'Unknown'}\n"
            f"Investment strategy (free text): {buyer.investment_strategy or 'Unknown'}\n"
            f"Notes (free text): {buyer.notes or 'Unknown'}"
            f"{buyer_meeting_notes_line}\n"
            f"Shortlisted candidates with deterministic scores: {candidates_context}"
        )

    def _build_repair_prompt(
        self,
        buyer: BuyerContext,
        profile: RequirementProfile,
        shortlist: list[tuple[SellerCandidate, CandidateScore]],
        invalid_raw: JsonObject,
        error: str | None,
    ) -> str:
        return (
            f"{self._build_prompt(buyer, profile, shortlist)}\n\n"
            f"Your previous response was: {invalid_raw}\n"
            f"It failed schema validation with this specific error: {error}\n"
            "Return only corrected, valid JSON that fixes exactly that problem — "
            "no prose, no markdown fences."
        )
