"""Stage 3 (§15-16). The Bedrock reasoning call receives the buyer's
requirement profile, the shortlisted sellers, and their deterministic
criterion scores/evidence — it is responsible for qualitative narrative
only: why a match works, why it was chosen over the alternatives, a
recommended pitch, and risks/gaps. It is never responsible for the numeric
score, hard-filter decisions, entity IDs, or database writes.
"""

from pydantic import ValidationError

from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.llm.domain.bedrock_client import BedrockClient, InferenceConfig
from app.modules.matching.domain.value_objects import CandidateScore
from app.modules.matching.schemas import ReasoningResult
from app.modules.requirements.domain.value_objects import RequirementProfile
from app.modules.sellers.domain.value_objects import SellerCandidate
from app.shared.types import render_meeting_notes_section


class MatchReasoningError(Exception):
    """Raised when Bedrock's reasoning output fails validation even after
    one bounded repair attempt. The caller must not fabricate a narrative —
    fail the run rather than present an unreasoned match (§32.E).
    """


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
    ) -> ReasoningResult:
        output_schema = ReasoningResult.model_json_schema()
        raw = await self._client.generate_reasoning(
            model_id=self._model_id,
            prompt=self._build_prompt(buyer, profile, shortlist),
            inference_config=self._inference_config,
            output_schema=output_schema,
        )
        result, error = self._validate(raw)

        if result is None:
            raw_retry = await self._client.generate_reasoning(
                model_id=self._model_id,
                prompt=self._build_repair_prompt(buyer, profile, shortlist, raw, error),
                inference_config=self._inference_config,
                output_schema=output_schema,
            )
            result, error = self._validate(raw_retry)

        if result is None:
            raise MatchReasoningError(
                f"Bedrock reasoning output for buyer_role={buyer.buyer_role_id} failed "
                "validation after one repair attempt"
            )
        return result

    @staticmethod
    def _validate(raw: dict) -> tuple[ReasoningResult | None, str | None]:
        try:
            return ReasoningResult.model_validate(raw), None
        except ValidationError as exc:
            return None, str(exc)

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
                "est_revenue": seller.est_revenue.model_dump() if seller.est_revenue else None,
                "est_ebitda": seller.est_ebitda.model_dump() if seller.est_ebitda else None,
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
        invalid_raw: dict,
        error: str | None,
    ) -> str:
        return (
            f"{self._build_prompt(buyer, profile, shortlist)}\n\n"
            f"Your previous response was: {invalid_raw}\n"
            f"It failed schema validation with this specific error: {error}\n"
            "Return only corrected, valid JSON that fixes exactly that problem — "
            "no prose, no markdown fences."
        )
