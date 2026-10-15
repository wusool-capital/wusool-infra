"""Buyer Requirement Service (§5). Extracts structured requirements from
`buyer_roles.investment_strategy`/`.notes` via Bedrock, using every other
already-structured `buyer_roles`/`organizations` field `BuyerContext` carries
(`known_fields`) as confirmed grounding rather than making the LLM re-derive
them from prose — `human_confirmed: true` only applies to what's actually in
`known_fields`, or in the advisor's own typed context for this run
(`source: advisor_context`). Never treats LLM-extracted values as
CRM-verified — every requirement carries provenance.

The Bedrock Port owns the validate-repair-retry-then-fail-closed policy
(`application/ports/llm.py`) — this service only builds the prompt/repair
prompt (business-content-aware) and converts the already-validated result
dict into the domain `RequirementProfile`. No `pydantic` import here: the
vendor-response schema (`providers/bedrock/schemas.py`) never crosses this
boundary.
"""

import logging
import re

from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS
from app.modules.matching_engine.application.errors import RequirementExtractionError
from app.modules.matching_engine.application.ports.llm import (
    BedrockClient,
    InferenceConfig,
)
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.overrides import apply_advisor_overrides
from app.modules.matching_engine.domain.matching.scoring import (
    describe_criteria,
    is_sector_criterion,
)
from app.modules.matching_engine.domain.meetings import render_meeting_notes_section
from app.modules.matching_engine.domain.requirements import (
    AdvisorLimits,
    HardRequirement,
    RequirementProfile,
    RequirementSource,
    SoftPreference,
)
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.money import parse_usd_amount
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

logger = logging.getLogger(__name__)

_SECTOR_BY_LOWER: dict[str, str] = {s.lower(): str(s) for s in SECTOR_FOCUS_OPTIONS}
_SECTOR_LIST = "; ".join(sorted(_SECTOR_BY_LOWER.values()))


_MODIFIER_SECTORS = frozenset({"AI / ML", "Technology", "Sharia-Compliant"})
# A relational phrase flips which side is the core business, so demotion is skipped.
_RELATIONAL = re.compile(r"\b(for|serving|serve|helps?|helping|that|which|to)\b", re.IGNORECASE)
_MODIFIER_SOFT_WEIGHT = 0.8


def _checked_value(item: JsonObject) -> str | None:
    """CRM-sourced rows pass through; advisor/LLM sectors must be CRM options."""
    value = item["value"]
    if value is None or item["source"] == "crm_field" or not is_sector_criterion(item["criterion"]):
        return value
    return _SECTOR_BY_LOWER.get(value.strip().lower())


def _is_dropped(item: JsonObject) -> bool:
    return item["value"] is not None and _checked_value(item) is None


def _demote_modifier_sectors(
    hard: list[HardRequirement], soft: list[SoftPreference], phrase: str | None
) -> tuple[list[HardRequirement], list[SoftPreference]]:
    # A modifier kept as a second hard sector lets modifier-only sellers pass the OR-ed filter.
    if not phrase or _RELATIONAL.search(phrase):
        return hard, soft
    rows = [
        h
        for h in hard
        if is_sector_criterion(h.criterion) and h.source == "advisor_context" and h.value
    ]
    flags = [h.value in _MODIFIER_SECTORS for h in rows]
    if all(flags) or not any(flags):
        return hard, soft
    demoted = [h for h, flag in zip(rows, flags, strict=True) if flag]
    have = {p.value for p in soft if is_sector_criterion(p.criterion)}
    added = [
        SoftPreference(h.criterion, h.value, _MODIFIER_SOFT_WEIGHT, "advisor_context", h.confidence)
        for h in demoted
        if h.value not in have
    ]
    return [h for h in hard if not any(h is d for d in demoted)], [*soft, *added]


# A limit is only trusted if the advisor's own words name what it measures. A
# misread "up to 10M" as an EV cap would remove sellers in SQL, so the model's
# reading is not enough on its own.
_TICKET_WORDS = re.compile(r"\b(tickets?|che(?:que|ck)s?|investment size)\b", re.IGNORECASE)
_EV_WORDS = re.compile(r"\b(ev|enterprise value|valuation|valued)\b", re.IGNORECASE)


def _advisor_limits(extracted: JsonObject, advisor_context: str | None) -> AdvisorLimits:
    if not advisor_context:
        return AdvisorLimits()
    limits = extracted.get("advisor_limits") or {}
    names_ticket = _TICKET_WORDS.search(advisor_context) is not None
    names_ev = _EV_WORDS.search(advisor_context) is not None
    return AdvisorLimits(
        ticket_min=parse_usd_amount(limits.get("ticket_min")) if names_ticket else None,
        ticket_max=parse_usd_amount(limits.get("ticket_max")) if names_ticket else None,
        ev_ceiling=parse_usd_amount(limits.get("ev_ceiling")) if names_ev else None,
    )


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

    async def extract(
        self, buyer: BuyerContext, *, next_version: int, advisor_context: str | None = None
    ) -> RequirementProfile:
        try:
            extracted = await self._client.extract_requirements(
                model_id=self._model_id,
                prompt=self._build_prompt(buyer, advisor_context),
                repair_prompt_builder=lambda invalid_raw, error: self._build_repair_prompt(
                    buyer, advisor_context, invalid_raw, error
                ),
                inference_config=self._inference_config,
            )
        except BedrockInvocationError as exc:
            raise RequirementExtractionError(
                f"Bedrock extraction output for buyer_role={buyer.buyer_role_id} failed "
                "validation after one repair attempt"
            ) from exc

        return self._to_domain(
            extracted, next_version, self._model_id, advisor_context=advisor_context
        )

    def _build_prompt(self, buyer: BuyerContext, advisor_context: str | None) -> str:
        # Every one of these is a real, already-structured buyer-side value
        # for one of `describe_criteria()`'s criteria — eligible for
        # `human_confirmed: true`. `target_geography`/`sector_focus` were
        # found missing here entirely on 2026-09-14 (a buyer with a real,
        # populated `target_geography` still produced an unrestricted seller
        # search, since nothing told the LLM it existed) — never put
        # `org_hq_country`/`org_region` in this dict: those are the buyer's
        # own HQ, not their target market, and would get misread as a
        # confirmed `geography` value otherwise (see `context_fields` below).
        known_fields = {
            "model": buyer.model,
            "mandate_status": buyer.mandate_status,
            "ebitda_floor": buyer.ebitda_floor,
            "ebitda_ceiling": buyer.ebitda_ceiling,
            "check_size_min": buyer.check_size_min,
            "check_size_max": buyer.check_size_max,
            "ev_ceiling": buyer.ev_ceiling,
            "deal_structure_tolerance": buyer.deal_structure_tolerance,
            "earnout_tolerance": buyer.earnout_tolerance,
            "profitable_only": buyer.profitable_only,
            "target_region (broad regions the buyer targets, e.g. GCC, MENA; together "
            "with target_country a union -- emit one geography requirement per value)": (
                buyer.target_region
            ),
            "target_country (specific countries the buyer targets, in addition to "
            "target_region)": buyer.target_country,
            "target_vertical (the sector this buyer role is for — the hard `sector` unless "
            "the advisor names another business type)": buyer.target_vertical,
        }
        # Real CRM data, but none of it is itself a criterion value — folded
        # into `strategic_thesis`/`ideal_target_description` grounding
        # instead, same as free text, never `human_confirmed: true`.
        context_fields = {
            "org_hq_country (buyer's own HQ -- NOT their target geography, "
            "see target_region/target_country above for that)": buyer.org_hq_country,
            "org_region (buyer's own HQ region -- NOT their target geography)": buyer.org_region,
            "org_type": buyer.org_type,
            "org_sector_focus (the buyer organization's own sector interests — context "
            "only, never a requirement)": buyer.org_sector_focus,
            "org_categories": buyer.org_categories,
            "org_description": buyer.org_description,
            "notable_investments": buyer.notable_investments,
            "key_personnel": buyer.key_personnel,
            "acquisition_enrichment": buyer.acquisition_enrichment,
            "prior_gcc_acquisition": buyer.prior_gcc_acquisition,
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
        advisor_context_block = (
            "\nAdvisor context (typed by the advisor for this search — free text, "
            f"but a human's own instruction): {advisor_context}\n"
            "A hard_requirement that states an explicit, unambiguous constraint from "
            "this advisor context (e.g. a stated floor or required region) must use "
            "source advisor_context and human_confirmed: true. The advisor's context "
            "OVERRIDES any conflicting structured buyer field: when it restates a "
            "criterion (e.g. a different geography), emit only the advisor's value and "
            "never the conflicting CRM one. Fill `advisor_limits` only from an explicit "
            "statement in this advisor context: `ticket_min`/`ticket_max` for a stated "
            "cheque or ticket size range, `ev_ceiling` for a stated enterprise-value cap. "
            "Write each as `USD <amount>`; leave the rest null, and never derive them "
            "from the structured buyer fields. A bare amount with no keyword saying "
            'what it measures (e.g. just "up to 10M") sets NO limit: use `ticket_*` '
            "only when the advisor says ticket/cheque/check/investment size, and "
            "`ev_ceiling` only when they say EV/enterprise value/valuation. Revenue or "
            "EBITDA amounts are never limits. Vague preferences, hedged wording, or "
            "anything inferred rather than stated belong in soft_preferences with "
            "source llm_extracted instead."
            if advisor_context
            else ""
        )
        return (
            "Extract structured buyer requirements as strict JSON matching this "
            "shape: {hard_requirements: [{criterion, value, source, confidence, "
            "human_confirmed}], soft_preferences: [{criterion, value, weight, "
            "source, confidence}], strategic_thesis, ideal_target_description, "
            "scoring_rubric: {criterion: weight}, data_confidence: 0-1, "
            "advisor_limits: {ticket_min, ticket_max, ev_ceiling}, search_phrase}. "
            "`source` must be one of crm_field/advisor_context/llm_extracted/"
            "llm_inferred/unavailable. `confidence` (on each hard_requirement/soft_preference "
            "item) must be exactly one of the strings high/medium/low — never a "
            "numeric score. `data_confidence` (top-level, separate field) is the "
            "only place a 0-1 number belongs. Only use `human_confirmed: true` "
            "for facts already "
            "present in the structured buyer fields below, or an explicit "
            "constraint in the advisor context section (source advisor_context) "
            "— everything else derived from free text is "
            "`llm_extracted`/`llm_inferred` and `human_confirmed: false`. "
            "Never invent a CRM field; if information "
            "is absent, omit it or mark it `unavailable`. Any field below shown "
            "as `(not provided)` has no data at all — never copy the literal "
            "text `(not provided)` into `strategic_thesis`, "
            "`ideal_target_description`, or any hard_requirement/soft_preference "
            "value; omit that field's contribution entirely instead. Return only "
            "the JSON object itself — no markdown code fences, no explanation "
            "before or after it.\n\n"
            "`criterion` on every hard_requirement and soft_preference must be "
            "exactly one of these names — they are the only ones actually "
            "checked against real seller data, anything else is silently "
            "unscored:\n"
            f"{describe_criteria()}\n"
            "Revenue and EBITDA values must be written as `USD <amount>` "
            "(for example `USD 50M`); never emit bare numbers or another currency.\n"
            "Every `sector` value must be copied exactly from this list of CRM sectors — "
            "never free text: "
            f"{_SECTOR_LIST}\n"
            "SECTOR PROCEDURE — follow in order:\n"
            "1. Does the advisor context name a business type (what companies to find)? If NOT, "
            "emit no advisor-sourced sector at all; the hard `sector` is the buyer's "
            "`target_vertical` (source crm_field) and `search_phrase` is null. The buyer "
            "organization's own sector interests are context, never a requirement.\n"
            "2. If YES, it fully REPLACES `target_vertical` (do not emit the CRM sector). "
            "Split the "
            "phrase into CORE (the noun: what the company is or does) and MODIFIERS (adjectives: "
            "AI, digital, tech-enabled, green, Sharia-compliant, robotics-driven, online, "
            "'X-style', 'X-like').\n"
            "3. CORE -> hard `sector` rows, source advisor_context, human_confirmed true: pick "
            "the 1-3 closest CRM sectors, one row each (OR-ed alternatives). MODIFIERS -> "
            "soft_preferences `sector` rows, weight 0.8, source advisor_context, never hard. "
            "The advisor context outranks every CRM value and every inference: whatever "
            "it states is source advisor_context. The CORE is decided by "
            "the noun, not the adjective: 'AI dental clinics' -> hard 'Dental / Specialist "
            "Clinics', soft 'AI / ML'; 'green real estate developers' -> hard 'Real Estate "
            "Development', soft 'Renewable Energy / CleanTech'; 'robotics-driven warehouse "
            "operators' -> hard 'Logistics / 3PL / Freight', soft 'Robotics / Automation'.\n"
            "4. 'X for / serving / helping Y' -> X is CORE (hard), Y is soft: 'AI tools for asset "
            "managers' -> hard 'AI / ML', soft 'Asset Management'. 'AI asset or wealth "
            "managers' -> hard 'Asset Management' + 'Family Office / Wealth Management', soft "
            "'AI / ML'.\n"
            "Worked example — advisor says 'AI tools for asset managers': hard_requirements has "
            "ONE sector row {criterion: sector, value: 'AI / ML', source: advisor_context, "
            "human_confirmed: true}; soft_preferences has {criterion: sector, value: 'Asset "
            "Management', weight: 0.8, source: advisor_context}. Asset Management must NOT be "
            "a hard row. Same shape for 'software for clinics', 'AI platforms serving "
            "insurers', 'analytics for hotels', 'startups that help family offices'.\n"
            "5. Several different business types joined by and/or/commas are all CORE (hard, "
            "OR-ed): 'clinics, dental or pharma'.\n"
            "6. Map slang to the CRM sector that names the business: cloud kitchens / food tech / "
            "food delivery -> 'Food Manufacturing / FoodTech' + 'Food & Beverage / QSR'; "
            "robo-advisors / wealthtech -> 'Fintech' + 'Family Office / Wealth Management'; "
            "payments / BNPL / lending -> 'Fintech'; crypto / web3 -> 'Web3 / Blockchain / "
            "Digital Assets' (hard); marketplace -> 'Retail / E-Commerce'; pet clinics -> 'Pet "
            "Care'; last-mile / warehouse -> 'Logistics / 3PL / Freight'; solar -> 'Renewable "
            "Energy / CleanTech'; car dealerships -> 'Automotive'; healthcare -> 'Healthcare "
            "Services / Clinics'; tech / technology companies -> 'Technology'; software -> "
            "'Enterprise Software' + 'SaaS / Cloud'. If nothing is close, emit "
            "the hard row with the advisor's own words as value (it is checked afterwards). "
            "The advisor's words may be in any language.\n"
            "7. Geography: when the advisor names places, emit only those as hard `geography` "
            "(source advisor_context) and none of the CRM target_region/target_country. Use "
            "full country names ('Saudi Arabia', 'United Arab Emirates') or region names "
            "(GCC, MENA), never abbreviations like KSA.\n"
            "8. `sector_exclusion`: 'not X', 'except X', 'avoid X' -> a hard `sector_exclusion` "
            "with the CRM sector for X.\n"
            "9. Top-level `search_phrase`: whenever step 2 applies (even a single word), 2-6 words "
            "naming the type of business with its "
            "modifiers (e.g. 'AI wealth management'), built ONLY from the advisor's words, "
            "never from CRM fields, and with no place names. Null when the advisor named no "
            "business type (for example only a place, an amount, a quality like 'profitable', "
            "or text that is not a request).\n"
            "If something in the free text below doesn't fit any of these "
            "names, do not invent a new criterion for it — fold it into "
            "`strategic_thesis` or `ideal_target_description` instead, both of "
            "which the reasoning step still reads.\n\n"
            f"Organization: {buyer.org_name}\n"
            f"Known structured buyer fields (eligible for human_confirmed: "
            f"true): {known_fields}\n"
            f"Additional buyer/organization context (real CRM data, but NOT "
            f"itself a confirmed criterion value — ground strategic_thesis/"
            f"ideal_target_description with it, never emit it as a "
            f"human_confirmed hard_requirement): {context_fields}\n"
            f"Investment strategy (free text): "
            f"{buyer.investment_strategy or '(not provided)'}\n"
            f"Notes (free text): {buyer.notes or '(not provided)'}"
            f"{meeting_notes_block}"
            f"{advisor_context_block}"
        )

    def _build_repair_prompt(
        self,
        buyer: BuyerContext,
        advisor_context: str | None,
        invalid_raw: JsonObject,
        error: str | None,
    ) -> str:
        return (
            f"{self._build_prompt(buyer, advisor_context)}\n\n"
            f"Your previous response was: {invalid_raw}\n"
            f"It failed schema validation with this specific error: {error}\n"
            "Return only corrected, valid JSON that fixes exactly that problem — "
            "no prose, no markdown fences."
        )

    @staticmethod
    def _to_domain(
        extracted: JsonObject, version: int, model_id: str, *, advisor_context: str | None
    ) -> RequirementProfile:
        has_advisor_context = bool(advisor_context)

        def source_of(item: JsonObject) -> RequirementSource:
            # Without typed context nothing can honestly be advisor-sourced; a
            # model claiming so would otherwise gain elimination power.
            if item["source"] == "advisor_context" and not has_advisor_context:
                return "llm_extracted"
            return item["source"]

        raw_items = [*extracted["hard_requirements"], *extracted["soft_preferences"]]
        for item in raw_items:
            if _is_dropped(item):
                logger.warning("extraction_sector_not_in_vocabulary value=%s", item["value"])
        # The model fills the phrase from CRM sectors when the advisor named only
        # a place or quality. A dropped advisor sector still counts: it is unmappable.
        named_business_type = any(
            is_sector_criterion(i["criterion"])
            and i["value"] is not None
            and source_of(i) == "advisor_context"
            for i in raw_items
        )
        search_phrase = extracted.get("search_phrase") if named_business_type else None

        hard, soft = _demote_modifier_sectors(
            [
                HardRequirement(
                    criterion=h["criterion"],
                    value=_checked_value(h),
                    source=source_of(h),
                    confidence=h["confidence"],
                    human_confirmed=h["human_confirmed"] and source_of(h) == h["source"],
                )
                for h in extracted["hard_requirements"]
                if not _is_dropped(h)
            ],
            [
                SoftPreference(
                    criterion=s["criterion"],
                    value=_checked_value(s),
                    weight=s["weight"],
                    source=source_of(s),
                    confidence=s["confidence"],
                )
                for s in extracted["soft_preferences"]
                if not _is_dropped(s)
            ],
            search_phrase or advisor_context,
        )
        profile = RequirementProfile(
            hard_requirements=hard,
            soft_preferences=soft,
            strategic_thesis=extracted["strategic_thesis"],
            ideal_target_description=extracted["ideal_target_description"],
            scoring_rubric=extracted["scoring_rubric"],
            data_confidence=extracted["data_confidence"],
            generated_by_model=model_id,
            version=version,
            advisor_limits=_advisor_limits(extracted, advisor_context),
            search_phrase=search_phrase,
        )
        return apply_advisor_overrides(profile)
