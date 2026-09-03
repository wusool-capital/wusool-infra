"""Stage 1 structured filtering (§9-10) and Stage 2 deterministic scoring
(§11-13). Pure domain logic — no I/O, no Bedrock, no SQL. Both stages share
one criterion-evaluation function so "would this eliminate a candidate" and
"what's this candidate's sub-score for this criterion" never disagree.

`CRITERION_REGISTRY` is the single source of truth for which criterion names
this engine can actually check against real seller data. The extraction
prompt (`application/requirements.py`) renders its allowed-criteria list from
this same registry via `describe_criteria`, so the LLM is never told about
(or free to invent) a criterion name this engine can't evaluate — the two
can't drift apart because there's only one list.
"""

from dataclasses import dataclass

from app.modules.matching_engine.domain.matching.entities import (
    CandidateScore,
    CriterionScore,
    DataConfidence,
    FilterSkipped,
)
from app.modules.matching_engine.domain.requirements import (
    RequirementProfile,
    RequirementSource,
)
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.utilities.domain.money import parse_usd_amount


@dataclass(frozen=True)
class _CriterionSpec:
    synonyms: frozenset[str]
    description: str


CRITERION_REGISTRY: dict[str, _CriterionSpec] = {
    "revenue": _CriterionSpec(
        frozenset({"revenue", "minimum_revenue", "min_revenue", "revenue_floor"}),
        "Minimum seller revenue threshold, checked against the seller's est_revenue.",
    ),
    "ebitda": _CriterionSpec(
        frozenset({"ebitda", "minimum_ebitda", "min_ebitda", "ebitda_floor"}),
        "Minimum seller EBITDA threshold, checked against the seller's est_ebitda.",
    ),
    "geography": _CriterionSpec(
        frozenset({"geography", "geographic_focus", "region", "location"}),
        "Required seller geography, checked against the seller's geographic_focus/hq_country.",
    ),
    "sector": _CriterionSpec(
        frozenset({"sector", "industry", "sector_focus"}),
        "Required seller sector/industry, checked against the seller's sector_focus.",
    ),
    "sector_exclusion": _CriterionSpec(
        frozenset({"sector_exclusion", "excluded_sector", "sector_exclude"}),
        "A sector the seller must NOT operate in, checked against the seller's "
        "sector_focus (inverse match).",
    ),
    "client_type": _CriterionSpec(
        frozenset({"client_type"}),
        "Required seller client type, checked against the seller's client_type.",
    ),
    "outreach_tier": _CriterionSpec(
        frozenset({"outreach_tier"}),
        "Required seller outreach tier, checked against the seller's outreach_tier.",
    ),
    "relationship_status": _CriterionSpec(
        frozenset({"relationship_status"}),
        "Required seller relationship status, checked against the seller's relationship_status.",
    ),
    "appetite_signal": _CriterionSpec(
        frozenset({"appetite_signal"}),
        "Required seller appetite signal, checked against the seller's appetite_signal.",
    ),
}

_ALL_MAPPED_KEYS: frozenset[str] = frozenset().union(
    *(spec.synonyms for spec in CRITERION_REGISTRY.values())
)


def describe_criteria() -> str:
    """Renders the registry as a prompt-ready list of recognized criterion
    names — the extraction prompt's only source for "what criterion names
    exist", so it never has to be kept in sync by hand.
    """
    return "\n".join(f"- {name}: {spec.description}" for name, spec in CRITERION_REGISTRY.items())


# Local aliases onto the registry's synonym sets, purely for readability in
# `_evaluate_criterion` below — not a second copy of the data.
_REVENUE_KEYS = CRITERION_REGISTRY["revenue"].synonyms
_EBITDA_KEYS = CRITERION_REGISTRY["ebitda"].synonyms
_GEOGRAPHY_KEYS = CRITERION_REGISTRY["geography"].synonyms
_SECTOR_KEYS = CRITERION_REGISTRY["sector"].synonyms
_SECTOR_EXCLUSION_KEYS = CRITERION_REGISTRY["sector_exclusion"].synonyms
_CLIENT_TYPE_KEYS = CRITERION_REGISTRY["client_type"].synonyms
_OUTREACH_TIER_KEYS = CRITERION_REGISTRY["outreach_tier"].synonyms
_RELATIONSHIP_STATUS_KEYS = CRITERION_REGISTRY["relationship_status"].synonyms
_APPETITE_SIGNAL_KEYS = CRITERION_REGISTRY["appetite_signal"].synonyms


def normalize_criterion(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def is_monetary_criterion(name: str) -> bool:
    key = normalize_criterion(name)
    return key in _REVENUE_KEYS or key in _EBITDA_KEYS


def _parse_amount(text: str) -> float | None:
    """Parse the strict USD monetary requirement format."""
    return parse_usd_amount(text)


def _evaluate_criterion(
    criterion: str, value: str | None, candidate: SellerCandidate
) -> tuple[str, RequirementSource, float]:
    """Returns (result, data_backing, sub_score 0-100) for one criterion
    against one candidate. `data_backing="unavailable"` covers every case
    where the criterion has no seller-side mapping at all, or the mapped
    field isn't populated on this candidate, or the requirement's own value
    is missing/unparseable — never fabricated, always a neutral midpoint
    score rather than a silent Pass or Fail.
    """
    if value is None:
        return "Unknown", "unavailable", 50.0

    key = normalize_criterion(criterion)

    if key in _REVENUE_KEYS:
        if candidate.est_revenue is None or candidate.est_revenue.amount is None:
            return "Unknown", "unavailable", 50.0
        threshold = _parse_amount(value)
        if threshold is None:
            return "Unknown", "unavailable", 50.0
        passes = candidate.est_revenue.amount >= threshold
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _EBITDA_KEYS:
        if candidate.est_ebitda is None or candidate.est_ebitda.amount is None:
            return "Unknown", "unavailable", 50.0
        threshold = _parse_amount(value)
        if threshold is None:
            return "Unknown", "unavailable", 50.0
        passes = candidate.est_ebitda.amount >= threshold
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _GEOGRAPHY_KEYS:
        if not candidate.geographic_focus and not candidate.hq_country:
            return "Unknown", "unavailable", 50.0
        target = value.strip().lower()
        in_focus = any(target == g.strip().lower() for g in candidate.geographic_focus)
        in_hq = bool(candidate.hq_country) and target == candidate.hq_country.strip().lower()
        passes = in_focus or in_hq
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _SECTOR_KEYS:
        if not candidate.sector_focus:
            return "Unknown", "unavailable", 50.0
        target = value.strip().lower()
        passes = any(target == s.strip().lower() for s in candidate.sector_focus)
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _SECTOR_EXCLUSION_KEYS:
        if not candidate.sector_focus:
            return "Unknown", "unavailable", 50.0
        target = value.strip().lower()
        excluded = any(target == s.strip().lower() for s in candidate.sector_focus)
        return ("Fail" if excluded else "Pass"), "crm_field", (0.0 if excluded else 100.0)

    if key in _CLIENT_TYPE_KEYS:
        if not candidate.client_type:
            return "Unknown", "unavailable", 50.0
        passes = candidate.client_type.strip().lower() == value.strip().lower()
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _OUTREACH_TIER_KEYS:
        if not candidate.outreach_tier:
            return "Unknown", "unavailable", 50.0
        passes = candidate.outreach_tier.strip().lower() == value.strip().lower()
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _RELATIONSHIP_STATUS_KEYS:
        if not candidate.relationship_status:
            return "Unknown", "unavailable", 50.0
        passes = candidate.relationship_status.strip().lower() == value.strip().lower()
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    if key in _APPETITE_SIGNAL_KEYS:
        if not candidate.appetite_signal:
            return "Unknown", "unavailable", 50.0
        passes = candidate.appetite_signal.strip().lower() == value.strip().lower()
        return ("Pass" if passes else "Fail"), "crm_field", (100.0 if passes else 0.0)

    return "Unknown", "unavailable", 50.0


def apply_structured_filters(
    profile: RequirementProfile, candidates: list[SellerCandidate]
) -> tuple[list[SellerCandidate], list[FilterSkipped]]:
    """Stage 1 (§9-10). Missing-data pass-through is mandatory: a candidate
    is only eliminated when a mapped, populated seller field contradicts a
    human-confirmed hard requirement (§13 — an unconfirmed LLM-extracted hard
    requirement never eliminates on its own). Exactly one `filters_skipped`
    entry is recorded per criterion that couldn't be fully enforced across
    the whole candidate batch.
    """
    passed = list(candidates)
    filters_skipped: list[FilterSkipped] = []

    for requirement in profile.hard_requirements:
        key = normalize_criterion(requirement.criterion)

        if key not in _ALL_MAPPED_KEYS:
            filters_skipped.append(
                FilterSkipped(
                    criterion=requirement.criterion,
                    reason="no_mapping",
                    candidates_exempted=len(passed),
                )
            )
            continue

        if not requirement.human_confirmed:
            filters_skipped.append(
                FilterSkipped(
                    criterion=requirement.criterion,
                    reason="unconfirmed_llm_extraction",
                    candidates_exempted=len(passed),
                )
            )
            continue

        survivors = []
        exempted = 0
        for candidate in passed:
            result, data_backing, _ = _evaluate_criterion(
                requirement.criterion, requirement.value, candidate
            )
            if data_backing == "unavailable":
                exempted += 1
                survivors.append(candidate)
            elif result == "Fail":
                continue  # eliminated
            else:
                survivors.append(candidate)
        if exempted:
            filters_skipped.append(
                FilterSkipped(
                    criterion=requirement.criterion,
                    reason="no_populated_field",
                    candidates_exempted=exempted,
                )
            )
        passed = survivors

    return passed, filters_skipped


class ScoringEngine:
    """Stage 2 (§11-13). Deterministic, reproducible — never calls Bedrock,
    never queries the database. `confidence_multipliers` come from
    `Settings.confidence` (crm_field=1.0 and unavailable=0.0 are the fixed
    endpoints, added here rather than taking them as config since they are
    not configurable per §12).
    """

    def __init__(self, confidence_multipliers: dict[str, float]) -> None:
        self._multipliers: dict[str, float] = {
            "crm_field": 1.0,
            "unavailable": 0.0,
            **confidence_multipliers,
        }

    def _multiplier(self, data_backing: RequirementSource) -> float:
        return self._multipliers.get(data_backing, 0.0)

    def score(
        self,
        buyer_role_id: str,
        seller_role_id: str,
        profile: RequirementProfile,
        candidate: SellerCandidate,
    ) -> CandidateScore:
        criteria: list[CriterionScore] = []
        weighted_sum = 0.0
        weighted_confidence_sum = 0.0
        total_weight = 0.0

        # Hard requirements carry full weight and are always evaluated here
        # regardless of human_confirmed — §13: unconfirmed ones must still
        # influence scoring, they just can't eliminate at Stage 1.
        for requirement in profile.hard_requirements:
            if normalize_criterion(requirement.criterion) not in _ALL_MAPPED_KEYS:
                # An unrecognized criterion name has no seller-side field to
                # check — recorded for audit (dims/View Full Analysis) but
                # excluded from weight/weighted_sum/weighted_confidence_sum
                # entirely, rather than silently contributing a fabricated
                # neutral 50 that dilutes the real score.
                criteria.append(
                    CriterionScore(
                        criterion=requirement.criterion,
                        criterion_type="hard",
                        weight=None,
                        result="Unrecognized",
                        data_backing="unavailable",
                    )
                )
                continue

            weight = 1.0
            result, data_backing, sub_score = _evaluate_criterion(
                requirement.criterion, requirement.value, candidate
            )
            criteria.append(
                CriterionScore(
                    criterion=requirement.criterion,
                    criterion_type="hard",
                    weight=weight,
                    result=result,
                    data_backing=data_backing,
                )
            )
            weighted_sum += weight * sub_score
            weighted_confidence_sum += weight * self._multiplier(data_backing)
            total_weight += weight

        for preference in profile.soft_preferences:
            if normalize_criterion(preference.criterion) not in _ALL_MAPPED_KEYS:
                criteria.append(
                    CriterionScore(
                        criterion=preference.criterion,
                        criterion_type="soft",
                        weight=None,
                        result="Unrecognized",
                        data_backing="unavailable",
                    )
                )
                continue

            result, data_backing, sub_score = _evaluate_criterion(
                preference.criterion, preference.value, candidate
            )
            criteria.append(
                CriterionScore(
                    criterion=preference.criterion,
                    criterion_type="soft",
                    weight=preference.weight,
                    result=result,
                    data_backing=data_backing,
                )
            )
            weighted_sum += preference.weight * sub_score
            weighted_confidence_sum += preference.weight * self._multiplier(data_backing)
            total_weight += preference.weight

        overall_score = (weighted_sum / total_weight) if total_weight else 0.0
        confidence_value = (weighted_confidence_sum / total_weight) * 100.0 if total_weight else 0.0
        applicable = sum(1 for c in criteria if c.data_backing != "unavailable")

        return CandidateScore(
            buyer_role_id=buyer_role_id,
            seller_role_id=seller_role_id,
            overall_score=round(overall_score, 2),
            confidence=DataConfidence(
                value=round(confidence_value, 2),
                applicable_criteria=applicable,
                total_criteria=len(criteria),
            ),
            criteria=criteria,
        )


def rank_candidates(scores: list[CandidateScore]) -> list[CandidateScore]:
    """Ranks by `overall_score` descending. `data_confidence` is a separate
    signal, deliberately not part of the sort key (§12/§14) — a high-score,
    low-confidence match stays visibly distinct rather than being folded
    into a combined ranking number.
    """
    return sorted(scores, key=lambda s: s.overall_score, reverse=True)


def select_top_n(scores: list[CandidateScore], n: int) -> list[CandidateScore]:
    """§14: if fewer than `n` candidates are available, return however many
    exist rather than fabricating a third result."""
    return rank_candidates(scores)[:n]


def needs_web_fallback(scores: list[float], min_score: float) -> bool:
    """True when nothing in `scores` clears the qualifying threshold,
    including the empty-list case — a CRM shortlist can be non-empty but
    still every candidate a bad match (free-text-extracted hard
    requirements can't eliminate anyone at Stage 1), so this checks score
    quality rather than presence. Takes plain scores rather than a
    `MatchRunResult` to avoid this module importing back from
    `application/matching/use_cases.py`.
    """
    return not scores or max(scores) < min_score
