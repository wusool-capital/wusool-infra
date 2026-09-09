"""Every prompt, as a pure function. No I/O, no model ids, no token budgets —
those belong to `providers/bedrock/`.

Ported from the tool pages, where they were string literals inside the
browser bundle. Two deliberate changes from the originals, both explained in
`domain/readiness.py`: the advisory prompt loses its "TASK 2" (the referral
is computed, not asked for) and gains the two free-text answers the live
version never sees.

The response contracts in these prompts must stay in step with
`providers/bedrock/schemas.py` — the schema is what actually validates, but a
prompt asking for a differently-named field just produces a validation
failure the visitor experiences as an error.
"""

from app.modules.lead_magnets.domain.readiness import ReadinessAnswers


def readiness_score_prompt(
    *,
    founder: str,
    business: str,
    sector: str,
    revenue_range: str,
    country: str,
    answers: ReadinessAnswers,
) -> str:
    """The score, band, five dimensions and three recommendations.

    Unchanged from the live prompt other than its formatting: this is the one
    tool with no deterministic fallback, so its output shape is the contract
    the page renders directly.
    """

    def s(question: str) -> str:
        value = answers.score(question)
        return "not answered" if value is None else str(value)

    return f"""You are an expert M&A advisor at Wusool Capital, a Gulf and MENA boutique advisory firm helping MENA founders exit their businesses. You are warm, direct, and encouraging.

Founder: {founder} | Business: {business} | Sector: {sector} | Revenue: {revenue_range} | Country: {country}

FINANCIAL HEALTH (0=poor, 3=excellent):
- Financial statements quality: {s("q1")}/3
- Customer concentration risk: {s("q2")}/3
- Outstanding liabilities: {s("q3")}/3

TEAM & OPERATIONS:
- Business independence from founder: {s("q4")}/3
- Management team strength: {s("q5")}/3
- Process documentation: {s("q6")}/3

REVENUE QUALITY:
- Recurring revenue %: {s("q7")}/3
- Customer loyalty/tenure: {s("q8")}/3
- Revenue growth trend: {s("q9")}/3

LEGAL & STRUCTURE:
- Company registration: {s("q10")}/3
- Contract hygiene: {s("q11")}/3
- IP/asset ownership: {s("q12")}/3

GROWTH STORY:
- Buyer proposition clarity: {s("q13")}/3
- Buyer appeal in their words: "{answers.q14 or "Not provided"}"
- What held back growth: "{answers.q15 or "Not provided"}"

Respond with ONLY valid JSON (no markdown):
{{"overallScore":<0-100>,"scoreBand":"<Not Ready|Early Stage|Getting There|Nearly Ready|Exit Ready>","summaryParagraph":"<2-3 warm honest sentences. Use the business name. Acknowledge strengths first.>","dimensions":[{{"name":"Financial Health","score":<0-100>,"insight":"<1 specific actionable sentence>"}},{{"name":"Team & Operations","score":<0-100>,"insight":"<1 sentence>"}},{{"name":"Revenue Quality","score":<0-100>,"insight":"<1 sentence>"}},{{"name":"Legal & Structure","score":<0-100>,"insight":"<1 sentence>"}},{{"name":"Growth Story","score":<0-100>,"insight":"<1 sentence>"}}],"recommendations":[{{"title":"<short title>","detail":"<2 sentences, specific, plain English, no jargon>"}},{{"title":"<short title>","detail":"<2 sentences>"}},{{"title":"<short title>","detail":"<2 sentences>"}}]}}

Rules: Be honest, don't inflate scores. Recommendations address weakest areas. Personalise using business name and sector."""  # noqa: E501


def readiness_advisory_prompt(
    *,
    company: str | None,
    sector: str | None,
    revenue_range: str | None,
    score: float,
    band: str,
    answers: ReadinessAnswers,
) -> str:
    """The internal advisory note. Never shown to the visitor.

    The live version's "TASK 2 — RECOMMENDED REFERRAL" is deliberately gone:
    it asked the model to re-derive referrals from if-then conditions spelled
    out in English, which `build_advisory_content` already computes from the
    same thirteen integers. One task, one output, no drift.

    It also gains the two free-text answers. `generateAdvisory` iterates the
    scored questions only, so today the advisor's brief never sees the
    founder's own statement of what a buyer would want.
    """
    answer_lines = "\n".join(f"  - {text}: {label}" for text, label in answers.scored_labels())
    return f"""You are an internal analyst at Wusool Capital, an M&A advisory firm in the UAE. A potential sell-side client just completed our M&A Readiness assessment. Generate one internal CRM field — never shown to the client.

COMPANY CONTEXT
Name: {company or "Unknown"}
Sector: {sector or "Not specified"}
Annual Revenue: {revenue_range or "Not specified"}
M&A Readiness Score: {score:g}/100 ({band})

QUESTIONNAIRE ANSWERS
{answer_lines}

IN THEIR OWN WORDS
Why a buyer would want this business: "{answers.q14 or "Not provided"}"
What has held back growth: "{answers.q15 or "Not provided"}"

TASK — INTERNAL ADVISORY NOTE
Write a frank, direct brief (4-6 sentences) for the Wusool advisor taking the first call. Synthesise risks and opportunities holistically across all answers — not a list of flags, but a coherent read on the deal. Call out the single biggest deal risk, what needs to be resolved before any buyer introductions, and whether this company is worth prioritising now or in 6-12 months. Be direct. This is internal.

Deterministic checks for referrals and hard risk flags run separately and are already recorded — do not repeat them as a list. Add the judgement they cannot.

Respond with ONLY valid JSON, no markdown:
{{"priority":"<now|6-12 months>","note":"<string>"}}"""  # noqa: E501
