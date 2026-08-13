# How It Works — a worked example

This walks through one real run of the matching pipeline end to end, showing
the actual data at every stage. The buyer is a fictional example, **Acme
Capital**; the flow and field names match the real code.

Trigger: a user runs `/find-match Acme Capital` in Slack (or picks "Acme
Capital" from the buyer-selection modal if the name is ambiguous).

---

## Stage 0 — Buyer context load

`BuyerRepository` loads the `buyer_roles` row for Acme Capital and maps it
into a `BuyerContext` value object. Only these fields are carried forward —
everything else on `buyer_roles` (`key_contact_attio_id`,
`acquisition_enrichment`, `deals_introduced`, `deals_converted`, `raw_attio`)
is not used by the pipeline today.

```python
BuyerContext(
    buyer_role_id="8f2b...-uuid",
    org_attio_id="org_acme_capital",
    org_name="Acme Capital",
    model="Buy-and-build platform",
    mandate_status="Active",
    ebitda_floor=Money(amount=5_000_000, currency="AED"),
    check_size_min=Money(amount=20_000_000, currency="AED"),
    check_size_max=Money(amount=80_000_000, currency="AED"),
    ev_ceiling=Money(amount=150_000_000, currency="AED"),
    deal_structure_tolerance="Majority or full acquisition only",
    earnout_tolerance="Up to 20% of consideration",
    profitable_only=True,
    investment_strategy=(
        "We acquire profitable healthcare services businesses based in "
        "Saudi Arabia. We do not invest in fintech. Looking for founder-led "
        "operators with recurring revenue."
    ),
    notes="Met the principal at a Riyadh conference in March, strong appetite.",
    contact_person_id="ppl_12345",
)
```

---

## Stage 1 — Requirement extraction (Bedrock, one call)

`BuyerRequirementExtractionService` builds a prompt from `BuyerContext`: the
eight structured fields above go in as trusted "known fields", and
`investment_strategy` + `notes` go in as free text for the LLM to mine.

**Prompt sent to Bedrock (abbreviated):**

```
Extract structured buyer requirements as strict JSON matching this shape:
{hard_requirements: [...], soft_preferences: [...], strategic_thesis,
ideal_target_description, scoring_rubric, data_confidence}.
...
Organization: Acme Capital
Known structured buyer fields: {'model': 'Buy-and-build platform',
  'mandate_status': 'Active', 'ebitda_floor': Money(5,000,000 AED), ...}
Investment strategy (free text): We acquire profitable healthcare services
  businesses based in Saudi Arabia. We do not invest in fintech. Looking
  for founder-led operators with recurring revenue.
Notes (free text): Met the principal at a Riyadh conference in March,
  strong appetite.
```

**Bedrock's validated output → `RequirementProfile` (version 1 for this buyer):**

```python
RequirementProfile(
    hard_requirements=[
        HardRequirement(criterion="geography", value="Saudi Arabia",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="industry", value="healthcare",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="sector_exclusion", value="fintech",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="profitable_only", value="True",
                         source="crm_field", confidence="high",
                         human_confirmed=True),
    ],
    soft_preferences=[
        SoftPreference(criterion="recurring_revenue_model", value="True",
                        weight=0.6, source="llm_extracted", confidence="medium"),
        SoftPreference(criterion="founder_led", value="True",
                        weight=0.4, source="llm_extracted", confidence="medium"),
    ],
    strategic_thesis="Buy-and-build consolidation of profitable, "
                     "founder-led healthcare operators in Saudi Arabia.",
    ideal_target_description="A profitable, recurring-revenue healthcare "
                              "services business in KSA, founder still "
                              "operating day-to-day.",
    scoring_rubric={"geography": 1.0, "industry": 1.0,
                    "recurring_revenue_model": 0.6, "founder_led": 0.4},
    data_confidence=0.72,
    generated_by_model="anthropic.claude-...",
    version=1,
)
```

Note: `profitable_only` came from a real CRM field, so it's
`source="crm_field"`, `human_confirmed=True` — it **can** eliminate a
candidate at Stage 1. The three requirements pulled from free text are
`llm_extracted`/`human_confirmed=False` — they influence scoring but cannot
eliminate anyone on their own until a human confirms them.

This profile is persisted immediately onto the run's header row in
`match_results` (`rank IS NULL`), so the run stays queryable even if
everything after this fails.

---

## Stage 2 — Candidate retrieval + Stage 1 structured filtering

`StructuredCandidateRetriever` loads all eligible sellers (Branch 1: plain
structured query, no vector search yet) — say 172 seller orgs — then
`apply_structured_filters` runs each hard requirement against each
candidate's populated fields (`geographic_focus`, `sector_focus`,
`est_ebitda`, etc.), using the seller equivalent of `SellerCandidate`.

Three example sellers survive to illustrate the next stage:

| Seller | HQ / geo focus | Sector focus | Profitable |
|---|---|---|---|
| HealthTrack MENA | KSA | Healthcare | Yes |
| Fintech Target Co | UAE | Fintech | Yes |
| PaySecure Holdings | UAE | Fintech | Yes |

Filter outcome:
- `geography = Saudi Arabia` → HealthTrack **Pass**, Fintech Target Co **Fail**, PaySecure **Fail**
- `industry = healthcare` → HealthTrack **Pass**, the other two **Fail**
- `sector_exclusion = fintech` → HealthTrack **Pass** (not fintech), Fintech Target Co **Fail** (is fintech, hard-eliminated), PaySecure **Fail** (is fintech, hard-eliminated)
- `profitable_only` (CRM-backed) → all three **Pass**

Because `geography`/`industry`/`sector_exclusion` are `llm_extracted`
(unconfirmed), Stage 1 does **not** eliminate on them alone unless the
mapped seller field is actually populated and contradicts the requirement —
which it is here, so all three fail structurally on multiple hard
requirements. In a case where a seller's `sector_focus` were unpopulated,
that criterion would be exempted (`filters_skipped`) rather than silently
failing the seller.

`candidates_considered=172`, `candidates_filtered=<passed count>` are
recorded on the run row.

---

## Stage 3 — Deterministic scoring (`ScoringEngine`)

Every hard requirement gets weight `1.0`; soft preferences use their
extracted `weight`. Each criterion produces `(result, data_backing,
sub_score)` via the same evaluator Stage 1 uses (`_evaluate_criterion`), so
filtering and scoring never disagree.

**HealthTrack MENA** (passed the filter):

```python
CandidateScore(
    overall_score=91.4,       # weighted average of sub-scores
    confidence=DataConfidence(value=100.0, applicable_criteria=4, total_criteria=6),
    criteria=[
        CriterionScore(criterion="geography", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="industry", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="sector_exclusion", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="profitable_only", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="recurring_revenue_model", result="Unknown", data_backing="unavailable", weight=0.6),
        CriterionScore(criterion="founder_led", result="Unknown", data_backing="unavailable", weight=0.4),
    ],
)
```

`data_confidence` reflects how much of the score is grounded in real CRM
data (`crm_field`), not match quality — it's a separate signal from
`overall_score`, deliberately not folded into ranking (§12/§14).

`select_top_n` ranks all scored, filter-surviving candidates by
`overall_score` descending and keeps the top 3 (`STAGE3_TOP_N`).

---

## Stage 4 — Reasoning (Bedrock, one call, narrative only)

`MatchReasoningService` sends the buyer's profile plus the shortlisted
candidates' deterministic scores/criteria (never raw documents, never
un-shortlisted sellers) and asks for narrative only — it cannot change the
score, cannot re-run the filter, cannot invent facts not given to it.

**Output for HealthTrack MENA:**

```python
ReasoningResult.candidates[0] = {
    "seller_role_id": "...",
    "why_it_matches": (
        "HealthTrack MENA is the strongest match. Its sector_focus is "
        "confirmed Healthcare, directly aligning with Acme Capital's "
        "thesis. Its geographic_focus is KSA, precisely the target "
        "geography, and it is not in the excluded fintech sector."
    ),
    "why_chosen_over_alternatives": (
        "Ranked first because it is the only candidate to pass every hard "
        "requirement on real CRM data; the other two candidates are "
        "categorically excluded by both geography and sector."
    ),
    "recommended_pitch": (
        "Position Acme Capital's buy-and-build platform and its appetite "
        "for founder-led operators who want to keep running the business "
        "post-acquisition."
    ),
    "risks_and_gaps": (
        "Recurring-revenue mix and founder involvement are not yet "
        "confirmed in CRM data — verify directly before making an offer."
    ),
}
```

---

## Stage 5 — Persistence (one atomic transaction)

For each shortlisted candidate: a `match_scores` row (score breakdown +
reasoning text) is created first, then a `match_results` candidate row
(`rank`, `match_score`, `data_confidence`, the three narrative fields,
`status="PENDING_REVIEW"`) linked to it via `match_score_id`. The run's
header row is marked complete in the same transaction.

```
match_results (rank=1): HealthTrack MENA  — score 91.4, confidence 100, PENDING_REVIEW
match_results (rank=2): Fintech Target Co — score 17.0, confidence  67, PENDING_REVIEW
match_results (rank=3): PaySecure Holdings — score 17.0, confidence  67, PENDING_REVIEW
```

---

## Stage 6 — Slack delivery

The background task posts a placeholder ("🔍 Finding matches, please
wait…"), then edits that same message in place with the real result once
the run finishes:

```
Buyer: Acme Capital
─────────────────────────────
1. HealthTrack MENA — 91/100
   Data confidence: 100/100
   HealthTrack MENA is the strongest match. Its sector_focus is confirmed
   Healthcare, directly aligning with Acme Capital's thesis...
   [View Full Analysis] [Approve Match] [Reject Match]

2. Fintech Target Co — 17/100
   Data confidence: 67/100
   Fintech Target Co does not meaningfully match Acme Capital's acquisition
   criteria — excluded fintech sector, wrong geography...
   [View Full Analysis] [Approve Match] [Reject Match]

3. PaySecure Holdings — 17/100
   Data confidence: 67/100
   ...
```

---

## Stage 7 — Approve / Reject

Clicking **Approve Match** on HealthTrack MENA re-validates the row against
the database (never trusts the Slack payload's claimed state), checks the
state-machine transition (`PENDING_REVIEW → APPROVED` is legal;
`APPROVED → *` is not), updates the row, then:

1. Posts an ephemeral confirmation: `Match with HealthTrack MENA approved by @you.`
2. Rebuilds the same message from persisted state and replaces the original
   in place — HealthTrack MENA's buttons are gone, replaced with:
   `✅ APPROVED by @you`, while the other two candidates still show their
   buttons (each is decided independently).

**View Full Analysis** posts an ephemeral message rendered entirely from the
already-persisted `MatchAnalysis` (run + candidates + scores) — it never
re-calls Bedrock, so it's instant and cheap, and always shows exactly what
was scored and reasoned, not a fresh (possibly different) re-run.
