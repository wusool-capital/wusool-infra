"""The M&A Readiness questionnaire, its deterministic advisory rules, and the
band translation — all ported from the live tool, all pure.

Three things here are load-bearing and were wrong in the original:

1. **The referral is computed, not asked for.** The live prompt's "TASK 2"
   asks the model to re-derive referrals from if-then conditions written out
   in English — conditions `build_advisory_content` already computes from the
   same thirteen integers. The rules own the referral; the model is kept for
   the note, which is genuine synthesis.

2. **Compose, don't overwrite.** `index.js` does
   `advisoryNote = ai.internalAdvisoryNote || null`, replacing the
   deterministic note wholesale. So a hard flag like "DEAL RISK: Single
   customer exceeds 50% of revenue … do not refer" *vanishes* whenever the
   model's prose does not happen to repeat it. `merge_advisory` keeps the
   rules' output and lets the model add to it.

3. **q14 and q15 reach the advisory.** `generateAdvisory` iterates the
   thirteen scored questions only and never sees the two free-text answers,
   even though they are the most direct statement of what a buyer would want
   and what has held the business back.
"""

from dataclasses import dataclass, fields
from enum import StrEnum


class QuestionId(StrEnum):
    """The thirteen scored questions, by the same `q1`..`q13` identifiers
    `ReadinessAnswers`' own dataclass fields already use. A misspelled
    `QuestionId.Q1` fails at definition time; a misspelled `"q1"` string
    literal here would just silently produce a `QUESTION_OPTIONS` entry
    nothing ever looks up."""

    Q1 = "q1"
    Q2 = "q2"
    Q3 = "q3"
    Q4 = "q4"
    Q5 = "q5"
    Q6 = "q6"
    Q7 = "q7"
    Q8 = "q8"
    Q9 = "q9"
    Q10 = "q10"
    Q11 = "q11"
    Q12 = "q12"
    Q13 = "q13"


# Option title -> score, exactly as the live `READINESS_QUESTIONS` map keys
# them. Kept for the prompt's own labelling and for validating an inbound
# answer against the set its question actually offers.
QUESTION_OPTIONS: dict[str, dict[int, str]] = {
    QuestionId.Q1: {
        3: "Fully audited by external firm",
        2: "Accountant-prepared, not audited",
        1: "In progress",
        0: "Internal spreadsheets only",
    },
    QuestionId.Q2: {
        0: "One customer >50% of revenue",
        1: "One customer 30-50%",
        3: "No single customer >30%",
    },
    QuestionId.Q3: {
        3: "None — everything clean",
        1: "Minor issues being resolved",
        0: "Significant open issues",
    },
    QuestionId.Q4: {
        3: "Yes — strong independent team",
        2: "Mostly — some gaps",
        1: "Unlikely — key decisions need me",
        0: "No — fully dependent on me",
    },
    QuestionId.Q5: {
        3: "Strong across key functions",
        2: "1-2 good people relied on heavily",
        0: "Mostly me and junior staff",
    },
    QuestionId.Q6: {
        3: "Yes — clear SOPs",
        1: "Partially",
        0: "Not really — lives in people's heads",
    },
    QuestionId.Q7: {3: "80%+", 2: "50-80%", 1: "20-50%", 0: "Under 20%"},
    QuestionId.Q8: {3: "3+ years", 2: "1-3 years", 1: "Under 1 year", 0: "No repeat customers"},
    QuestionId.Q9: {
        3: "Growing 20%+ per year",
        2: "Growing steadily",
        1: "Flat",
        0: "Declining or inconsistent",
    },
    QuestionId.Q10: {
        3: "Fully registered, all licences current",
        1: "Mostly — minor gaps to sort",
        0: "Not fully — registration gaps exist",
    },
    QuestionId.Q11: {
        3: "All significant contracts signed",
        2: "Most — some still informal",
        0: "Mostly handshakes and trust",
    },
    QuestionId.Q12: {
        3: "Company owns all — clearly registered",
        2: "Most — some pending formal transfer",
        0: "Unclear — some assets in personal name",
    },
    QuestionId.Q13: {
        3: "Clear and documented",
        2: "Generally clear",
        1: "Somewhat clear",
        0: "Not defined",
    },
}

QUESTION_TEXT: dict[str, str] = {
    QuestionId.Q1: "Financial statements prepared by accountant?",
    QuestionId.Q2: "Customer concentration",
    QuestionId.Q3: "Outstanding tax, loan or legal issues",
    QuestionId.Q4: "Business continuity without owner (3-month test)",
    QuestionId.Q5: "Management team strength",
    QuestionId.Q6: "Business processes documented (SOPs)",
    QuestionId.Q7: "Revenue that is recurring or under contract",
    QuestionId.Q8: "Top 3 customer tenure",
    QuestionId.Q9: "Revenue trend last 2 years",
    QuestionId.Q10: "Regulatory standing and licence status",
    QuestionId.Q11: "Key contracts (customers, suppliers, employees) signed",
    QuestionId.Q12: "Ownership of IP, brand, software",
    QuestionId.Q13: "Clarity of buyer proposition",
}

# `index.js`'s BAND_MAP: the prompt's band -> the Attio option title. Not a
# cosmetic rename — writing the prompt's own wording to Attio would miss the
# select option and fail the write.
_ATTIO_BAND = {
    "not ready": "Early",
    "early stage": "Early",
    "getting there": "Developing",
    "nearly ready": "Sale Ready",
    "exit ready": "Market Ready",
}


class RevenueRange(StrEnum):
    """The five revenue bands the readiness form's `<select>` offers, exactly
    as `revenue_range_midpoint_usd()` looks them up after `.lower().strip()`.
    Member names are plain identifiers since the values themselves (`$`, an
    en-dash) are not legal Python identifier characters."""

    UNDER_1M = "under $1m"
    ONE_TO_5M = "$1m – $5m"
    FIVE_TO_15M = "$5m – $15m"
    FIFTEEN_TO_50M = "$15m – $50m"
    OVER_50M = "$50m+"


# Midpoints for the revenue *range* the readiness form collects (it asks for a
# band, not a figure). USD — no conversion anywhere.
_REVENUE_MIDPOINT_USD = {
    RevenueRange.UNDER_1M: 500_000.0,
    RevenueRange.ONE_TO_5M: 3_000_000.0,
    RevenueRange.FIVE_TO_15M: 10_000_000.0,
    RevenueRange.FIFTEEN_TO_50M: 32_500_000.0,
    RevenueRange.OVER_50M: 75_000_000.0,
}


@dataclass(frozen=True)
class ReadinessAnswers:
    """One submission's answers. Explicit fields rather than a `dict` so a
    typo is a check-time error, and so the thirteen scored questions are
    visibly distinct from the two free-text ones.
    """

    q1: int | None = None
    q2: int | None = None
    q3: int | None = None
    q4: int | None = None
    q5: int | None = None
    q6: int | None = None
    q7: int | None = None
    q8: int | None = None
    q9: int | None = None
    q10: int | None = None
    q11: int | None = None
    q12: int | None = None
    q13: int | None = None
    q14: str | None = None
    q15: str | None = None

    def score(self, question: str) -> int | None:
        value = getattr(self, question)
        return value if isinstance(value, int) else None

    def scored_labels(self) -> list[tuple[str, str]]:
        """`(question text, chosen option label)` for every answered scored
        question, in questionnaire order — what the advisory prompt reads.
        """
        labels: list[tuple[str, str]] = []
        for field in fields(self):
            if field.name not in QUESTION_TEXT:
                continue
            value = self.score(field.name)
            if value is None:
                continue
            option = QUESTION_OPTIONS[field.name].get(value, f"Value: {value}")
            labels.append((QUESTION_TEXT[field.name], option))
        return labels


@dataclass(frozen=True)
class AdvisoryContent:
    referral: str | None = None
    advisory_note: str | None = None


def attio_band(band: str | None) -> str | None:
    """Prompt band -> Attio option title, falling through unchanged for
    anything unrecognised so a prompt change surfaces as a failed option
    lookup rather than a silently dropped value."""
    if not band:
        return None
    return _ATTIO_BAND.get(band.lower().strip(), band)


def revenue_range_midpoint_usd(revenue_range: str | None) -> float | None:
    if not revenue_range:
        return None
    return _REVENUE_MIDPOINT_USD.get(revenue_range.lower().strip())


def build_advisory_content(answers: ReadinessAnswers) -> AdvisoryContent:
    """The deterministic half of the advisory — ported verbatim from the live
    `buildAdvisoryContent`, including its exact strings, which land in Attio
    text fields a human reads.

    These are the conditions the prompt's TASK 2 asks a model to re-derive.
    Computing them here instead means the referral cannot drift with model
    temperature.
    """
    referrals: list[str] = []
    notes: list[str] = []

    q1 = answers.score("q1")
    if q1 is not None and q1 <= 1:
        referrals.append("Audit / accounting partner (UAE Freezone Service Providers list)")
        notes.append(
            "Financial statements not accountant-prepared. "
            "Refer for audit/accounting before buyer process."
        )

    q2 = answers.score("q2")
    if q2 == 0:
        notes.append(
            "DEAL RISK: Single customer exceeds 50% of revenue. "
            "High buyer concern - do not refer until concentration is addressed."
        )
    elif q2 == 1:
        notes.append(
            "Customer concentration 30-50%. "
            "Moderate risk - confirm diversification plan on first call."
        )

    q3 = answers.score("q3")
    if q3 == 0:
        referrals.append("Legal / compliance partner (significant open tax or legal issues)")
        notes.append(
            "Significant tax or legal issues outstanding. "
            "Legal referral required before proceeding."
        )
    elif q3 == 1:
        notes.append(
            "Minor tax or legal issues in progress. Confirm resolution status on first call."
        )

    q4 = answers.score("q4")
    if q4 is not None and q4 <= 1:
        notes.append(
            "Founder dependency risk: business is heavily reliant on the owner. "
            "Key buyer concern - address on readiness call."
        )

    if answers.score("q6") == 0:
        notes.append(
            "No documented processes or SOPs. Recommend operational preparation before listing."
        )

    if answers.score("q10") == 0:
        referrals.append("Legal / licensing partner (registration or licence gaps identified)")
        notes.append("Regulatory standing incomplete. Must resolve before any buyer introductions.")

    q12 = answers.score("q12")
    if q12 == 0:
        referrals.append("IP / legal partner (key assets or brand held in personal name)")
        notes.append(
            "IP and/or brand assets in personal name. "
            "Must be formally transferred to company before sale process."
        )
    elif q12 == 2:
        referrals.append("IP / legal partner (some assets pending formal transfer to company)")
        notes.append("Some IP/brand assets require formal transfer to company entity.")

    return AdvisoryContent(
        referral="; ".join(referrals) if referrals else None,
        advisory_note=" | ".join(notes) if notes else None,
    )


def merge_advisory(rules: AdvisoryContent, model_note: str | None) -> AdvisoryContent:
    """Rules always survive; the model adds on top.

    The live code assigns the model's note over the deterministic one, so a
    hard flag disappears whenever the prose does not repeat it. The referral
    is never taken from the model at all.
    """
    if not model_note:
        return rules
    if not rules.advisory_note:
        return AdvisoryContent(referral=rules.referral, advisory_note=model_note)
    return AdvisoryContent(
        referral=rules.referral,
        advisory_note=f"{rules.advisory_note} | {model_note}",
    )
