"""Buyer Requirement Service (§5). Extracts structured requirements from
`buyer_roles.investment_strategy`/`.notes` via Bedrock. Never treats
LLM-extracted values as CRM-verified — every requirement carries provenance.

The Bedrock Port owns the validate-repair-retry-then-fail-closed policy
(`application/ports/llm.py`) — this service only builds the prompt/repair
prompt (business-content-aware) and converts the already-validated result
dict into the domain `RequirementProfile`. No `pydantic` import here: the
vendor-response schema (`providers/bedrock/schemas.py`) never crosses this
boundary.
"""

from app.modules.matching_engine.application.errors import RequirementExtractionError
from app.modules.matching_engine.application.ports.llm import (
    BedrockClient,
    InferenceConfig,
)
from app.modules.matching_engine.application.provider_errors import BedrockInvocationError
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.scoring import describe_criteria
from app.modules.matching_engine.domain.meetings import render_meeting_notes_section
from app.modules.matching_engine.domain.requirements import (
    HardRequirement,
    RequirementProfile,
    SoftPreference,
)
from app.modules.utilities.domain.json_types import JsonObject


class BuyerRequirementExtractionService:
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

    async def extract(self, buyer: BuyerContext, *, next_version: int) -> RequirementProfile:
        try:
            extracted = await self._client.extract_requirements(
                model_id=self._model_id,
                prompt=self._build_prompt(buyer),
                repair_prompt_builder=lambda invalid_raw, error: self._build_repair_prompt(
                    buyer, invalid_raw, error
                ),
                inference_config=self._inference_config,
            )
        except BedrockInvocationError as exc:
            raise RequirementExtractionError(
                f"Bedrock extraction output for buyer_role={buyer.buyer_role_id} failed "
                "validation after one repair attempt"
            ) from exc

        return self._to_domain(extracted, next_version, self._model_id)

    def _build_prompt(self, buyer: BuyerContext) -> str:
        known_fields = {
            "model": buyer.model,
            "mandate_status": buyer.mandate_status,
            "ebitda_floor": buyer.ebitda_floor,
            "check_size_min": buyer.check_size_min,
            "check_size_max": buyer.check_size_max,
            "ev_ceiling": buyer.ev_ceiling,
            "deal_structure_tolerance": buyer.deal_structure_tolerance,
            "earnout_tolerance": buyer.earnout_tolerance,
            "profitable_only": buyer.profitable_only,
        }
        meeting_notes_section = render_meeting_notes_section(
            buyer.meeting_notes,
            total_char_budget=self._meeting_notes_char_budget,
            subject_name=buyer.org_name,
        )
        meeting_notes_block = (
            f"\n{meeting_notes_section}\n"
            "Any hard_requirement or soft_preference derived only from these "
            "meeting notes must use source llm_extracted/llm_inferred and "
            "human_confirmed: false — never crm_field/human_confirmed: true. "
            "Prefer folding meeting-note content into strategic_thesis or "
            "ideal_target_description over minting a new structured "
            "requirement from it at all."
            if meeting_notes_section
            else ""
        )
        return (
            "Extract structured buyer requirements as strict JSON matching this "
            "shape: {hard_requirements: [{criterion, value, source, confidence, "
            "human_confirmed}], soft_preferences: [{criterion, value, weight, "
            "source, confidence}], strategic_thesis, ideal_target_description, "
            "scoring_rubric: {criterion: weight}, data_confidence: 0-1}. "
            "`source` must be one of crm_field/llm_extracted/llm_inferred/"
            "unavailable. `confidence` (on each hard_requirement/soft_preference "
            "item) must be exactly one of the strings high/medium/low — never a "
            "numeric score. `data_confidence` (top-level, separate field) is the "
            "only place a 0-1 number belongs. Only use `human_confirmed: true` "
            "for facts already "
            "present in the structured buyer fields below — everything derived "
            "from free text is `llm_extracted`/`llm_inferred` and "
            "`human_confirmed: false`. Never invent a CRM field; if information "
            "is absent, omit it or mark it `unavailable`. Return only the JSON "
            "object itself — no markdown code fences, no explanation before or "
            "after it.\n\n"
            "`criterion` on every hard_requirement and soft_preference must be "
            "exactly one of these names — they are the only ones actually "
            "checked against real seller data, anything else is silently "
            "unscored:\n"
            f"{describe_criteria()}\n"
            "Revenue and EBITDA values must be written as `USD <amount>` "
            "(for example `USD 50M`); never emit bare numbers or another currency.\n"
            "If something in the free text below doesn't fit any of these "
            "names, do not invent a new criterion for it — fold it into "
            "`strategic_thesis` or `ideal_target_description` instead, both of "
            "which the reasoning step still reads.\n\n"
            f"Organization: {buyer.org_name}\n"
            f"Known structured buyer fields: {known_fields}\n"
            f"Investment strategy (free text): {buyer.investment_strategy or 'Unknown'}\n"
            f"Notes (free text): {buyer.notes or 'Unknown'}"
            f"{meeting_notes_block}"
        )

    def _build_repair_prompt(
        self, buyer: BuyerContext, invalid_raw: JsonObject, error: str | None
    ) -> str:
        return (
            f"{self._build_prompt(buyer)}\n\n"
            f"Your previous response was: {invalid_raw}\n"
            f"It failed schema validation with this specific error: {error}\n"
            "Return only corrected, valid JSON that fixes exactly that problem — "
            "no prose, no markdown fences."
        )

    @staticmethod
    def _to_domain(extracted: JsonObject, version: int, model_id: str) -> RequirementProfile:
        return RequirementProfile(
            hard_requirements=[
                HardRequirement(
                    criterion=h["criterion"],
                    value=h["value"],
                    source=h["source"],
                    confidence=h["confidence"],
                    human_confirmed=h["human_confirmed"],
                )
                for h in extracted["hard_requirements"]
            ],
            soft_preferences=[
                SoftPreference(
                    criterion=s["criterion"],
                    value=s["value"],
                    weight=s["weight"],
                    source=s["source"],
                    confidence=s["confidence"],
                )
                for s in extracted["soft_preferences"]
            ],
            strategic_thesis=extracted["strategic_thesis"],
            ideal_target_description=extracted["ideal_target_description"],
            scoring_rubric=extracted["scoring_rubric"],
            data_confidence=extracted["data_confidence"],
            generated_by_model=model_id,
            version=version,
        )
