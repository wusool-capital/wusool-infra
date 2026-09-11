"""Every prompt, as a pure function. No I/O, no model ids, no token budgets —
those belong to `providers/bedrock/`.

Ported from the tool pages, where they were string literals inside the
browser bundle. Two deliberate changes from the originals, both explained in
`domain/readiness.py`: the advisory prompt loses its "TASK 2" (the referral
is computed, not asked for) and gains the two free-text answers the live
version never sees.

The response contracts in these prompts must stay in step with the Bedrock
response models in `domain/shared/schemas.py` — the schema is what actually
validates, but a prompt asking for a differently-named field just produces a
validation failure the visitor experiences as an error.
"""

from app.modules.lead_magnets.domain.readiness.readiness import ReadinessAnswers


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


def enrich_prompt(*, company: str, domain: str, page_text: str, sector_list: list[str]) -> str:
    """Company description and sector, from the company's own page.

    Adapted from the live prompt in one necessary way: it instructed the
    model to "use web search to find and read the company's actual website".
    Bedrock cannot search for Claude at all, so the page is fetched by
    Firecrawl and passed in. That is a straight improvement here — the site
    is known from the domain, so there was never anything to search *for*.

    The prohibition on inferring from the name is kept verbatim and is the
    load-bearing instruction: company names are routinely generic words with
    no relation to the business.
    """
    sectors = ", ".join(sector_list)
    page = page_text.strip()[:6000]
    return f"""Read the company's own website content below, then provide TWO things in JSON format only (no markdown, no backticks, no preamble):

Company name: {company}
Domain: {domain}

WEBSITE CONTENT
{page or "(the page could not be fetched)"}

Base your answer strictly on the content above, which is from the real operating company at this domain. Do NOT guess from the company name, and do NOT rely on the dictionary or linguistic meaning of the name.

Then provide:
1. "description": A 25 to 40 word professional company description, third person, suitable for an investor deck. Focus on what the company actually does, its value proposition, target market, and business model. No marketing language, no CTAs, no em dashes. Stay within 25 to 40 words.

2. "sector": Select the SINGLE most accurate sector from this list: [{sectors}]. Return ONLY one sector name exactly as written in the list.

If the content above is missing or says nothing about what the business does, set description to an empty string and sector to an empty string rather than guessing.

Respond with ONLY valid JSON: {{"description":"...","sector":"..."}}"""  # noqa: E501


ENRICH_SYSTEM_PROMPT = (
    "You are a senior investment analyst at an M&A advisory firm. You produce "
    "institutional-quality company descriptions. You never use em dashes. You write in a "
    "professional, precise tone suitable for investor presentations. Never infer what a "
    "company does from its name alone, since company names are often generic words, "
    "dictionary terms, or unrelated to the actual business."
)

ANALYST_SYSTEM_PROMPT = (
    "You are a senior M&A analyst at an investment bank, with full authority to overrule an "
    "automated sector tag. Automated classifiers routinely mislabel businesses: a physical "
    "nursery gets tagged as EdTech because its description mentions education; a childcare "
    "operator gets tagged as a baby-products company because both involve children. Your job "
    "is to determine what the business ACTUALLY is and to build the valuation inputs a banker "
    "would actually use. Be precise with financial data. Never use em dashes."
)


def analyze_prompt(
    *,
    company: str,
    domain: str,
    sector: str,
    description: str,
    geography: str,
    revenue: float,
    ebitda: float,
    sector_list: list[str],
    website_text: str = "",
) -> str:
    """Sector judgement, DCF assumptions, dataset matching terms, the
    strategic read and the readiness scorecard.

    This is the live analyst call minus its comparables and discount steps,
    which move to `/compare`. The split is forced rather than chosen:
    comparables need grounded search, which on Bedrock means the Firecrawl
    two-pass pipeline, and that is a different shape of call entirely. It
    also lets the two run in parallel, which is why the preview is ready when
    the loading screen ends.
    """
    sectors = ", ".join(sector_list)
    website = f"Website: {website_text[:900]}\n" if website_text else ""
    return f"""Analyse this company and return the correct valuation inputs.

Company: {company}
Domain: {domain}
Auto-assigned sector tag (may be WRONG): {sector}
Description: {description}
{website}Geography: {geography}
Revenue: ${revenue:,.0f}
EBITDA: ${ebitda:,.0f}

STEP 1 - Judge the tag. The tool's fixed sector list is:
{sectors}

Decide honestly whether any of these genuinely fits the business model. Set sector_fit to "good" if one is a real match, or "poor" if the closest option would mislead a valuation (for example tagging a physical, real-estate-heavy service business into a software category). If "poor", still name the closest available tag in closest_existing_sector, but describe the true sector in effective_sector.

STEP 2 - Illiquidity and size discounts. This target has ${revenue:,.0f} revenue while listed peers are typically far larger. Recommend the discount to apply to peer multiples, as whole-number percentages, reflecting private-company illiquidity plus the size gap.

STEP 3 - DCF assumptions appropriate to the REAL business model (a capital-light software business and a capex-heavy physical operator should not share assumptions).

STEP 4 - Dataset matching terms. The tool holds proprietary M&A and VC datasets tagged with vertical names drawn from the sector list above. Return the terms from that list that should be used to find genuinely comparable deals for this business. Do not invent multiples; just name the matching terms.

STEP 5 - Strategic read. Give exactly 3 strengths (pros), 3 risks (cons) and 2 forward-looking insights, each specific to the REAL business model, not to the auto-assigned tag. Titles 8-15 words, bodies 40-60 words. No generic statements that could apply to any company.

STEP 6 - Readiness scorecard. Score revenue_scale, profitability and market_context from 0-100 with a 15-25 word note each, referencing only the actual figures given above. If a figure was not provided, score 50 and say what is missing. Do not invent growth or retention metrics. Also give overall_grade (A+ to D), overall_label (3-5 words) and a 40-60 word summary.

Never use em dashes. Never wrap text in ** markdown.

Respond with ONLY valid JSON, no markdown, no backticks:
{{"sector_fit":"good|poor","closest_existing_sector":"...","effective_sector":"...","rationale":"one or two sentences on what the business really is and why the tag does or does not fit","discounts":{{"revenue_discount_pct":50,"ebitda_discount_pct":50}},"dcf":{{"revGrowth":0,"ebitMarginImpr":0,"daaPct":0,"capexPct":0,"nwcPct":0,"termGrowth":0}},"transaction_search_terms":["..."],"vc_search_terms":["..."],"pros":[{{"title":"...","body":"..."}}],"cons":[{{"title":"...","body":"..."}}],"insights":[{{"title":"...","body":"..."}}],"fundraise":{{"revenue_scale":{{"score":0,"note":"..."}},"profitability":{{"score":0,"note":"..."}},"market_context":{{"score":0,"note":"..."}},"overall_grade":"...","overall_label":"...","summary":"..."}}}}"""  # noqa: E501


def compare_query_prompt(
    *, company: str, sector: str, description: str, geography: str = ""
) -> str:
    """Pass one of the comparables pipeline: search queries, nothing else.

    Queries **only**, and the constraint is not stylistic. Asked for
    candidate companies as well, the cheap model confidently returned a
    property developer and an insurance company as comparables for an
    interior fit-out business, with invented tickers — which would then have
    misled the selecting model in pass two.
    """
    region = f"\nGeography: {geography}" if geography else ""
    return f"""Write web search queries that would surface listed companies genuinely comparable to the business below, for a trading comparables table.

Company: {company}
Sector: {sector}
Description: {description}{region}

Rules:
- Return search queries ONLY. Do not name any company, ticker or figure.
- Between 3 and 6 queries. Each should be something you would actually type into a search engine.
- Aim queries at listed peers and their reported enterprise value, revenue and EBITDA.
- Include at least one query aimed at GCC or MENA-listed peers where that is plausibly relevant.

Respond with ONLY valid JSON: {{"queries":["...","..."]}}"""  # noqa: E501


def compare_select_prompt(
    *,
    company: str,
    sector: str,
    description: str,
    revenue: float,
    search_results: list[tuple[str, str, str]],
) -> str:
    """Pass two: pick the comparables out of what search actually returned.

    Figures must come from the results. The alternative was observed
    directly: told it could use its own knowledge, the model invented
    tickers. Accuracy and quantity trade off here — the honest answer is
    fewer comparables, and the shortfall is filled from the static sector
    set rather than by letting the model make figures up.
    """
    formatted = "\n\n".join(
        f"[{i + 1}] {title}\n{url}\n{snippet}"
        for i, (title, url, snippet) in enumerate(search_results)
    )
    return f"""Select the listed companies a banker would genuinely put in a trading comparables table for the business below, using ONLY the search results provided.

Company: {company}
Sector: {sector}
Description: {description}
Revenue: ${revenue:,.0f}

SEARCH RESULTS
{formatted or "(no results were returned)"}

Rules:
- Use ONLY companies and figures that appear in the results above. Do not add a company from memory, and do not estimate a figure that is not there.
- Each company must be currently listed and not taken private.
- Report EV, revenue and EBITDA in millions of USD. Omit a figure you cannot source by setting it to null.
- Include regional comparables (GCC, MENA-listed) where genuinely relevant.
- Returning fewer good matches is correct. Do NOT pad the list with weak fits, and do NOT invent anything to reach a target count.
- If the results contain no credible listed peer, return an empty list.

Respond with ONLY valid JSON: {{"comps":[{{"co":"Name","tk":"TICKER","ev":0,"rev":0,"ebitda":0}}]}}"""  # noqa: E501


def buyer_qualification_prompt(
    *,
    org_name: str,
    org_type: list[str],
    sector_focus: list[str],
    target_geography: list[str],
    check_size_min: float | None,
    check_size_max: float | None,
    prior_gcc_acquisition: str | None,
) -> str:
    """Internal only, mirroring `readiness_advisory_prompt`: one paragraph of
    synthesis, never shown to the applicant. There is nothing deterministic
    to compute here — unlike readiness's hard flags, a buyer application has
    no rule-derived score for the model to add judgement on top of, so the
    whole note is the model's read."""

    def money(low: float | None, high: float | None) -> str:
        if low is None and high is None:
            return "Not specified"
        if low is None:
            return f"up to ${high:,.0f}"
        if high is None:
            return f"${low:,.0f}+"
        return f"${low:,.0f} - ${high:,.0f}"

    return f"""You are an internal analyst at Wusool Capital, an M&A advisory firm in the UAE. A prospective buyer just applied to our Buyer Network. Generate one internal CRM field — never shown to the applicant.

APPLICANT
Organization: {org_name}
Type: {", ".join(org_type) or "Not specified"}
Sector preference: {", ".join(sector_focus) or "Not specified"}
Target geography: {", ".join(target_geography) or "Not specified"}
Typical check size: {money(check_size_min, check_size_max)}
Prior GCC acquisition: {prior_gcc_acquisition or "Not provided"}

TASK — INTERNAL QUALIFICATION NOTE
Write a frank, direct brief (3-5 sentences) for the Wusool advisor deciding whether to introduce deals to this buyer. Judge fit and credibility from what was submitted alone — do not assume facts not given. Call out anything that looks like a mismatch (an unusually broad mandate, an implausible check size, no prior GCC experience for an ambitious mandate) and whether this buyer is worth prioritising for warm introductions now or worth a qualifying call first. Be direct. This is internal.

Respond with ONLY valid JSON, no markdown:
{{"priority":"<introduce now|qualify first>","note":"<string>"}}"""  # noqa: E501
