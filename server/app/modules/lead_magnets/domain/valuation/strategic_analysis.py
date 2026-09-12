"""Deterministic fallback for `/analyze`'s pros/cons/insights.

Ported from the live tool's `generateStrategicAnalysis` (Bedrock unreachable
today produces a bare error, unlike every other tool's AI call — this is
what closes that gap). Every regex, condition, and paragraph of copy below
was extracted programmatically from the source HTML rather than hand-typed,
to eliminate transcription risk on ~30 paragraphs a real prospective client
would read: a Node harness ran the original function with sentinel inputs
and dumped its pools/fallbacks/insights as JSON, and this file's pool and
insight tables were generated from that JSON. Verified equivalent to the
original across 113 generated test cases spanning every signal combination
and every margin/fundraise/geography boundary (see
`tests/unit/test_strategic_analysis.py`).

`sector_fit`, `discounts`, `dcf`, `transaction_search_terms`,
`vc_search_terms` and `fundraise` — the rest of `/analyze`'s response — have
no equivalent in the original source; it never had a fallback for them
either. Only pros/cons/insights are deterministic.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategicPoint:
    title: str
    body: str


@dataclass(frozen=True)
class StrategicAnalysisResult:
    pros: tuple[StrategicPoint, ...]
    cons: tuple[StrategicPoint, ...]
    insights: tuple[StrategicPoint, ...]


_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "isPremium": re.compile(
        r"premium|luxury|high.end|bespoke|artisan|crafted|superior.quality|finest|exclusive.design",
        re.IGNORECASE,
    ),
    "hasBrandHeritage": re.compile(
        r"heritage|tradition|legacy|inspired by|reimagined|years of|founded|storied|generation|\btrunk\b",
        re.IGNORECASE,
    ),
    "isPersonalised": re.compile(
        r"personal|curated|tailored|bespoke|custom|individual|handpick", re.IGNORECASE
    ),
    "isSubscription": re.compile(
        r"subscription|membership|recurring|monthly plan|annual plan", re.IGNORECASE
    ),
    "isSustainable": re.compile(
        r"sustain|eco|green|ethical|responsible|organic|planet|carbon|circular", re.IGNORECASE
    ),
    "isInnovative": re.compile(
        r"innovat|disrupt|pioneer|\bfirst\b|transform|revolution|reinvent|reimagined", re.IGNORECASE
    ),
    "isMarketplace": re.compile(
        r"marketplace|two.sided|connect.*buyer|platform.*seller|network.*supplier", re.IGNORECASE
    ),
    "hasDataAI": re.compile(
        r"\bai\b|machine.learn|data.driven|intelligence|predictive|algorithm|personaliz",
        re.IGNORECASE,
    ),
    "isB2BDesc": re.compile(
        r"enterprise|b2b|business.to.business|corporate|workforce", re.IGNORECASE
    ),
    "isPhysical": re.compile(
        r"hardware|device|manufactur|suitcase|luggage|apparel|garment|physical.product|goods\b",
        re.IGNORECASE,
    ),
    "isSoftwareDigital": re.compile(r"software|platform|cloud|\bapp\b|digital|saas", re.IGNORECASE),
    "hasCommunity": re.compile(r"community|network|social|members|\bclub\b|tribe", re.IGNORECASE),
    "isNiche": re.compile(
        r"niche|specialist|boutique|curated|exclusive|artisan|bespoke", re.IGNORECASE
    ),
    "isTravelLifestyle": re.compile(
        r"travel|luggage|suitcase|journey|adventure|explorer|nomad|voyag", re.IGNORECASE
    ),
    "isFashionLifestyle": re.compile(
        r"fashion|apparel|clothing|wardrobe|\bstyle\b|outfit|\bwear\b", re.IGNORECASE
    ),
    "isConsumerBrand": re.compile(
        r"consumer|retail|shopper|direct.to|\bd2c\b|everyday", re.IGNORECASE
    ),
    "isGlobal": re.compile(r"global|international|worldwide|\bworld\b|cross.border", re.IGNORECASE),
    "isGCCGeo": re.compile(
        r"uae|united arab emirates|saudi|qatar|bahrain|kuwait|oman|jordan", re.IGNORECASE
    ),
    "isB2BSector": re.compile(
        r"saas|cybersecurity|fintech|payments|logistics|supply chain|future of work", re.IGNORECASE
    ),
}

_SIGNAL_SUBJECT: dict[str, str] = {
    "isPremium": "desc",
    "hasBrandHeritage": "desc",
    "isPersonalised": "desc",
    "isSubscription": "desc",
    "isSustainable": "desc",
    "isInnovative": "desc",
    "isMarketplace": "combo",
    "hasDataAI": "desc",
    "isB2BDesc": "combo",
    "isPhysical": "desc",
    "isSoftwareDigital": "combo",
    "hasCommunity": "desc",
    "isNiche": "desc",
    "isTravelLifestyle": "desc",
    "isFashionLifestyle": "combo",
    "isConsumerBrand": "combo",
    "isGlobal": "desc",
    "isGCCGeo": "geo",
    "isB2BSector": "sectorL",
}


def _signals(*, description: str, sector: str, geography: str) -> dict[str, bool]:
    """Every regex carries `/i` in the original, so — unlike the source,
    which separately lowercases `desc`/`sector` before building `combo` —
    nothing here needs lowercasing first; `re.IGNORECASE` already covers it.
    """
    desc = description or ""
    subjects = {
        "desc": desc,
        "combo": f"{desc} {sector or ''}",
        "geo": geography or "",
        "sectorL": sector or "",
    }
    return {
        name: bool(pattern.search(subjects[_SIGNAL_SUBJECT[name]]))
        for name, pattern in _SIGNAL_PATTERNS.items()
    }


def _pro_pool(company: str, signals: dict[str, bool]) -> list[tuple[bool, StrategicPoint]]:
    return [
        (
            signals["isPremium"] and signals["hasBrandHeritage"],
            StrategicPoint(
                title="""Heritage craft narrative creates durable brand defensibility""",
                body="""A brand rooted in both premium craftsmanship and heritage storytelling occupies emotional territory that well-funded competitors cannot replicate through marketing spend alone. This positioning converts customers into brand advocates and supports sustainable pricing premiums over commodity alternatives.""",
            ),
        ),
        (
            signals["isPremium"] and not signals["hasBrandHeritage"],
            StrategicPoint(
                title="""Premium positioning commands structural pricing power""",
                body=f"""By operating in the premium segment, {company} competes on quality and brand identity rather than price, creating structural insulation from commodity-level competition and enabling higher gross margins than mass-market peers at comparable revenue scale.""",
            ),
        ),
        (
            signals["hasBrandHeritage"] and not signals["isPremium"],
            StrategicPoint(
                title="""Heritage narrative creates authentic, hard-to-replicate differentiation""",
                body="""A brand story rooted in heritage or tradition occupies emotional territory that well-funded challengers cannot replicate through marketing spend alone, providing durable differentiation that transcends product features and resonates with quality-conscious consumers.""",
            ),
        ),
        (
            signals["isPersonalised"],
            StrategicPoint(
                title="""Personalisation creates compounding switching costs and retention leverage""",
                body="""Products and services built around individual preferences develop switching costs that grow with each interaction, as the experience becomes increasingly tailored to the customer. This dynamic supports above-average retention rates, higher lifetime value, and word-of-mouth referral loops.""",
            ),
        ),
        (
            signals["isSubscription"],
            StrategicPoint(
                title="""Recurring revenue model converts transactions into a predictable annuity stream""",
                body="""A subscription or membership structure provides revenue predictability that one-time transaction models cannot match, supporting reliable financial planning, higher customer lifetime value multiples, and a quality-of-earnings premium that is reflected directly in exit valuations.""",
            ),
        ),
        (
            signals["hasDataAI"],
            StrategicPoint(
                title="""Data and AI capabilities create a widening proprietary moat""",
                body=f"""Businesses that convert user interactions into proprietary datasets and AI-driven personalisation build structural advantages that compound over time. The performance gap between {company}'s model and a new entrant's widens with every additional data point, making competitive displacement progressively more difficult.""",
            ),
        ),
        (
            signals["isMarketplace"],
            StrategicPoint(
                title="""Marketplace dynamics carry inherent network effect defensibility""",
                body="""Two-sided platform mechanics create self-reinforcing defensibility: each incremental participant increases the platform's value for all others, making it structurally costly for buyers and sellers to migrate to a less liquid alternative and creating a compounding barrier to new entrant displacement.""",
            ),
        ),
        (
            signals["isSustainable"],
            StrategicPoint(
                title="""ESG alignment opens premium distribution channels and investor pools""",
                body="""A demonstrably sustainable product or supply chain resonates with a structurally growing segment of high-intent consumers, while simultaneously unlocking access to ESG-mandated institutional investors and retail distribution partners who apply sustainability screens to product selection.""",
            ),
        ),
        (
            signals["isTravelLifestyle"],
            StrategicPoint(
                title="""Travel is a structurally growing, high-spend, aspirational category""",
                body="""The travel goods market benefits from secular growth in global travel volumes, the accelerating premiumisation of everyday accessories, and the rise of a globally mobile affluent class. These tailwinds provide a supportive demand backdrop that a well-positioned brand can translate into above-market growth rates.""",
            ),
        ),
        (
            signals["isFashionLifestyle"] and not signals["isTravelLifestyle"],
            StrategicPoint(
                title="""Fashion and lifestyle brands command emotional loyalty that transcends product utility""",
                body="""Consumer loyalty in fashion is driven by identity and self-expression rather than purely functional value, creating a brand-customer relationship that sustains repeat purchase rates through seasonal cycles and supports organic word-of-mouth acquisition at significantly lower cost than paid channels.""",
            ),
        ),
        (
            signals["isB2BDesc"],
            StrategicPoint(
                title="""Enterprise customers deliver contractual revenue visibility and embedded stickiness""",
                body="""B2B and enterprise-facing revenue typically carries multi-year contracts, formal renewal processes, and embedded workflows that create high switching costs, producing predictable, high-quality revenue streams that command a premium over consumer-facing models at equivalent revenue scale.""",
            ),
        ),
        (
            signals["isInnovative"],
            StrategicPoint(
                title="""Innovation-led positioning establishes early category authority""",
                body="""Pioneering a new product category or approach creates brand equity and customer mindshare that is structurally difficult to displace, as markets tend to associate category leadership with the first credible player even as competition intensifies. This first-mover premium can persist well beyond the initial innovation window.""",
            ),
        ),
        (
            signals["hasCommunity"],
            StrategicPoint(
                title="""Community-driven growth reduces structural reliance on paid acquisition""",
                body="""A strong community or membership base generates organic referral loops and social proof that significantly reduce customer acquisition costs relative to pure paid digital marketing, creating a compounding advantage as the community grows and the brand's earned media value increases.""",
            ),
        ),
        (
            signals["isNiche"] and not signals["isMarketplace"],
            StrategicPoint(
                title="""Niche specialisation reduces competitive exposure and supports premium pricing""",
                body=f"""Operating in a focused, specialist segment means {company} competes on depth of expertise and curation rather than scale, reducing exposure to commoditisation and enabling a premium pricing architecture that broader, less specialised competitors cannot credibly replicate.""",
            ),
        ),
        (
            signals["isPhysical"] and not signals["isSoftwareDigital"],
            StrategicPoint(
                title="""Physical product creates tangible brand touchpoints at every use occasion""",
                body="""A physical product generates recurring, sensory brand reinforcement with every use, reinforcing brand identity and driving organic social sharing. This creates marketing leverage that pure digital products cannot achieve and builds emotional attachment that compounds into long-term loyalty.""",
            ),
        ),
        (
            signals["isSoftwareDigital"] and not signals["isB2BDesc"],
            StrategicPoint(
                title="""Digital delivery enables scalable global distribution with low marginal cost""",
                body=f"""A software or digital platform model decouples revenue growth from proportional cost growth, enabling {company} to serve an expanding global customer base without the infrastructure investment required by physical or service-intensive business models.""",
            ),
        ),
    ]


def _con_pool(company: str, signals: dict[str, bool]) -> list[tuple[bool, StrategicPoint]]:
    return [
        (
            signals["isPhysical"],
            StrategicPoint(
                title="""Physical supply chain introduces inventory, margin, and logistics risk""",
                body="""Managing a physical product requires ongoing capital allocation to inventory, exposure to freight cost volatility, supply chain disruption risk, and the operational complexity of quality control and returns management - all of which can compress margins and strain working capital at scale.""",
            ),
        ),
        (
            signals["isFashionLifestyle"] or signals["isTravelLifestyle"],
            StrategicPoint(
                title="""Seasonal cycles and trend sensitivity create demand planning complexity""",
                body="""Consumer preferences in fashion and lifestyle accessories shift across seasons and cultural moments, creating risk of unsold inventory that must be discounted or written off. Sophisticated demand forecasting and disciplined inventory management are non-negotiable operational capabilities at meaningful scale.""",
            ),
        ),
        (
            signals["isConsumerBrand"]
            or signals["isFashionLifestyle"]
            or signals["isTravelLifestyle"],
            StrategicPoint(
                title="""Rising paid digital acquisition costs erode consumer brand unit economics""",
                body="""Consumer-facing brands are heavily exposed to increasing CPMs across Meta, Google, and TikTok advertising ecosystems, as well as algorithm changes that can suddenly impair channel performance. CAC inflation risk is structural and persistent, requiring ongoing diversification into owned and earned channels.""",
            ),
        ),
        (
            signals["isNiche"],
            StrategicPoint(
                title="""Niche specialisation constrains the total addressable market ceiling""",
                body=f"""Deep specialisation, while protective, caps the scale of the addressable opportunity. Without a deliberate adjacency expansion strategy, {company} risks reaching a natural revenue ceiling that may limit its attractiveness to larger strategic acquirers who require material scale to justify a transaction.""",
            ),
        ),
        (
            signals["isPremium"],
            StrategicPoint(
                title="""Premium price points introduce cyclicality and volume sensitivity""",
                body="""Premium-positioned products see disproportionate demand softening in economic downturns as consumers trade down to more accessible alternatives. Managing this cyclicality requires product range diversification, geographic spread, or recurring revenue mechanics to smooth the earnings profile through cycles.""",
            ),
        ),
        (
            signals["isB2BDesc"],
            StrategicPoint(
                title="""Enterprise sales cycles are long, resource-intensive, and produce lumpy revenue""",
                body="""Selling to enterprise customers involves multi-stakeholder procurement, extended evaluation periods, legal review cycles, and significant pre-sales investment. This creates lumpy revenue recognition, unpredictable short-term performance, and high cost-of-sale that must be carefully managed against deal-level economics.""",
            ),
        ),
        (
            signals["isMarketplace"],
            StrategicPoint(
                title="""Achieving marketplace liquidity requires capital-intensive bilateral scaling""",
                body="""Building density on both sides of a marketplace simultaneously demands significant upfront investment and patient capital, with the risk that the platform fails to achieve critical mass before funding is exhausted. The chicken-and-egg problem is a well-documented and costly challenge for early-stage marketplace models.""",
            ),
        ),
        (
            signals["hasDataAI"],
            StrategicPoint(
                title="""AI and data-intensive operations carry high talent costs and key-person risk""",
                body="""Building and maintaining differentiated AI or data capabilities requires specialist engineering talent commanding significant compensation premiums in a globally competitive hiring market, creating persistent cost pressure, key-person dependency, and fragility if core technical contributors depart.""",
            ),
        ),
        (
            signals["isTravelLifestyle"],
            StrategicPoint(
                title="""Travel category carries macro disruption and cyclicality risk""",
                body="""Demand for travel goods and accessories correlates strongly with travel volumes, which are subject to external shocks including economic downturns, geopolitical instability, and public health events. These disruptions can produce sudden, acute revenue pressure that is difficult to hedge operationally.""",
            ),
        ),
        (
            signals["isSustainable"],
            StrategicPoint(
                title="""Sustainability claims require rigorous verification and expose the brand to scrutiny""",
                body="""ESG positioning creates reputational risk if supply chain practices, material sourcing, or manufacturing claims are challenged by media, regulators, or activist consumers. Robust third-party certification and transparent supply chain governance are essential to protecting the brand's sustainability credentials.""",
            ),
        ),
        (
            signals["isSubscription"],
            StrategicPoint(
                title="""Subscriber churn management demands continuous product and engagement investment""",
                body="""Recurring revenue models are only valuable if churn remains controlled. Even a modest increase in monthly cancellation rates can erode the subscriber base materially over time, requiring constant investment in product value delivery, engagement mechanics, and proactive retention programmes.""",
            ),
        ),
        (
            signals["isGlobal"],
            StrategicPoint(
                title="""International operations introduce currency, regulatory, and localisation complexity""",
                body="""Scaling across multiple geographies simultaneously exposes revenue to currency risk, demands localisation investment across language and cultural contexts, and requires navigation of divergent regulatory frameworks - all of which increase operational complexity and can dilute management bandwidth during critical growth phases.""",
            ),
        ),
        (
            signals["isPhysical"] and not signals["isSoftwareDigital"],
            StrategicPoint(
                title="""Working capital cycle for physical goods requires active cash management""",
                body="""Physical product businesses carry inventory on balance sheet and face a timing gap between cash outflow (manufacturing, shipping) and cash inflow (customer payment). As the business scales, this working capital cycle can become a meaningful constraint on growth velocity without proactive financing management.""",
            ),
        ),
    ]


def _pro_fallbacks(company: str, sector: str) -> list[StrategicPoint]:
    return [
        StrategicPoint(
            title="""Clear value proposition in a defined and growing market""",
            body=f"""{company} articulates a focused, differentiated proposition within its addressable market - the foundation for both sustainable commercial traction and investor conviction. A well-defined value proposition reduces acquisition friction and supports premium positioning relative to less differentiated alternatives.""",
        ),
        StrategicPoint(
            title="""Brand identity that compounds in value with scale""",
            body="""A distinct brand identity is a compounding asset that typically appreciates as revenue and customer reach grow, supporting pricing power, distribution leverage, and acquisition attractiveness over time. Strong brands consistently trade at a premium to commodity-positioned businesses at equivalent scale.""",
        ),
        StrategicPoint(
            title="""Sector positioned in a structural growth window""",
            body=f"""{company} operates in the {sector} sector, which continues to attract significant consumer demand, investor capital, and M&A activity - providing a supportive macro backdrop for a disciplined execution-driven growth strategy.""",
        ),
    ]


def _con_fallbacks(company: str, sector: str) -> list[StrategicPoint]:
    return [
        StrategicPoint(
            title=f"""Competitive intensity in {sector} compresses differentiation windows""",
            body=f"""The {sector} space is attracting well-funded incumbents and new entrants investing aggressively in adjacent categories, requiring sustained product innovation, brand investment, and customer experience excellence to maintain a defensible competitive position.""",
        ),
        StrategicPoint(
            title="""Operational scaling carries execution risk at each growth stage""",
            body="""The transition from current scale to the next revenue inflection point typically exposes gaps in team depth, systems architecture, and process maturity. Proactive investment in operational infrastructure before constraints become visible is critical to ensuring organisational capacity does not become the binding constraint on growth.""",
        ),
        StrategicPoint(
            title="""Customer acquisition and retention economics require ongoing optimisation""",
            body="""Sustained revenue growth demands continuous refinement of acquisition channel mix, retention mechanics, and cohort-level unit economics to ensure that increasing scale does not erode the fundamental profitability of each incremental customer relationship. CAC inflation and churn creep are silent margin destroyers when left unmanaged.""",
        ),
    ]


_INSIGHT_NEGATIVE_MARGIN_TITLE = (
    """Path to profitability is the highest-priority near-term milestone"""
)
_INSIGHT_NEGATIVE_MARGIN_BODY = """At a negative EBITDA margin, every dollar of cost reduction has a disproportionate impact on valuation across all methodologies. A credible, time-bound roadmap to break-even - with specific operating levers identified - will unlock a material valuation re-rating and substantially improve terms at the next fundraising round."""

_INSIGHT_LOW_MARGIN_TITLE = """Margin expansion to 15-20%+ is the highest-value operational focus"""
_INSIGHT_LOW_MARGIN_BODY = """Moving from the current {margin:.0f}% EBITDA margin to a 15-20%+ profile could increase the implied valuation by 1.5-2.5x under EBITDA multiple methodologies, with no requirement to grow the top line. The priority sequence should be: pricing review, COGS renegotiation, then headcount efficiency."""

_INSIGHT_STRONG_MARGIN_TITLE = """Strong margins create capacity to invest aggressively in growth"""
_INSIGHT_STRONG_MARGIN_BODY = """At {margin:.0f}% EBITDA margins, {company} has the operational leverage to reinvest in growth without deteriorating earnings quality. The strategic priority should shift to identifying the highest-ROI growth channels - geographic expansion, product adjacencies, or distribution partnerships - and deploying capital there with discipline."""

_INSIGHT_GCC_GEO_TITLE = """GCC-first depth before multi-region expansion"""
_INSIGHT_GCC_GEO_BODY = """Deepening penetration across GCC markets and codifying the operating playbook before entering higher-complexity regions (EU, US) will preserve capital and create a replicable, investable expansion blueprint. GCC-proven unit economics are increasingly valued by international growth investors as evidence of scalability."""

_INSIGHT_PRE_FUNDRAISE_TITLE = (
    """Institutional fundraising readiness: build the metrics story now"""
)
_INSIGHT_PRE_FUNDRAISE_BODY = """Pre-Series A investors will require three to six months of demonstrable momentum: consistent MoM revenue growth, improving unit economics, and a repeatable go-to-market motion. Investing in the data infrastructure to track and present these metrics compellingly will compress the fundraising timeline and improve deal terms."""

_INSIGHT_SERIES_B_READY_TITLE = (
    """Series B readiness requires demonstrating repeatability at scale"""
)
_INSIGHT_SERIES_B_READY_BODY = """Series B investors look for proof that the early-stage growth motion is repeatable and non-idiosyncratic. The key proof points are: NRR above 110% (if B2B), consistent new logo acquisition with declining CAC, and gross margin expansion. Building these metrics into the operating cadence now accelerates the next round."""

_INSIGHT_B2B_NRR_TITLE = (
    """Net revenue retention expansion delivers higher ROI than new logo acquisition"""
)
_INSIGHT_B2B_NRR_BODY = """In B2B models, improving NRR from baseline to 120%+ through structured upsell, cross-sell, and expansion programmes is typically 3-5x more capital-efficient than acquiring new logos. At {company}'s current revenue scale, a focused account expansion motion should be the primary commercial priority."""

_INSIGHT_LIFESTYLE_DATA_TITLE = (
    """Customer data infrastructure is the core long-term strategic asset"""
)
_INSIGHT_LIFESTYLE_DATA_BODY = """Every customer interaction - purchase history, preferences, returns, browsing behaviour - is a data point that compounds into a proprietary personalisation engine. Investing in data capture and CRM infrastructure now creates a competitive moat that is structurally difficult for incumbents to replicate, and substantially increases the business's attractiveness to acquirers."""

_INSIGHT_FALLBACK_1_TITLE = (
    """Strategic distribution partnerships can accelerate the growth trajectory"""
)
_INSIGHT_FALLBACK_1_BODY = """Identifying two to three non-competing platforms or channel partners with access to {company}'s target customer profile can materially compress the CAC curve while generating market validation signal that strengthens the next fundraising or M&A process. Prioritise partnerships offering co-marketing, embedded distribution, or data sharing benefits."""
_INSIGHT_FALLBACK_2_TITLE = """Operational excellence as a compounding competitive differentiator"""
_INSIGHT_FALLBACK_2_BODY = """Building repeatable, measurable operational processes across sales, customer success, and finance creates an advantage that compounds as the business scales and becomes increasingly difficult for less disciplined competitors to match. Operational excellence is the foundation of the margin expansion story that drives valuation multiple re-rating."""


def generate_strategic_analysis(
    *,
    company: str,
    description: str,
    sector: str,
    revenue: float,
    ebitda: float,
    geography: str,
    raised: bool = False,
    stage: str | None = None,
) -> StrategicAnalysisResult:
    """`pros`/`cons` are always exactly 3, `insights` always exactly 2 — the
    fallback lists exist so a short list is never possible.

    `raised`/`stage` are optional because `/analyze`'s request carries them
    as optional fields too: without them, two of the eight insight
    conditions (pre-fundraise readiness, Series B readiness) can never
    trigger, same as the live tool when a visitor skipped that step.
    """
    company = company or "The company"
    sector = sector or ""
    stage = stage or ""
    signals = _signals(description=description, sector=sector, geography=geography)

    matched_pros = [point for cond, point in _pro_pool(company, signals) if cond][:3]
    final_pros = list(matched_pros)
    for fallback in _pro_fallbacks(company, sector):
        if len(final_pros) >= 3:
            break
        final_pros.append(fallback)

    matched_cons = [point for cond, point in _con_pool(company, signals) if cond][:3]
    final_cons = list(matched_cons)
    for fallback in _con_fallbacks(company, sector):
        if len(final_cons) >= 3:
            break
        final_cons.append(fallback)

    # `margin===0` exactly matches none of the three branches below, same as
    # the source — not "fixed" here, since a business with literally zero
    # EBITDA is the one case with no margin-derived insight in the original.
    margin = (ebitda / revenue * 100) if revenue > 0 else 0.0
    insight_pool: list[StrategicPoint] = []
    if margin < 0:
        insight_pool.append(
            StrategicPoint(_INSIGHT_NEGATIVE_MARGIN_TITLE, _INSIGHT_NEGATIVE_MARGIN_BODY)
        )
    elif 0 < margin < 15:
        insight_pool.append(
            StrategicPoint(
                _INSIGHT_LOW_MARGIN_TITLE, _INSIGHT_LOW_MARGIN_BODY.format(margin=margin)
            )
        )
    elif margin >= 15:
        insight_pool.append(
            StrategicPoint(
                _INSIGHT_STRONG_MARGIN_TITLE,
                _INSIGHT_STRONG_MARGIN_BODY.format(margin=margin, company=company),
            )
        )

    if signals["isGCCGeo"]:
        insight_pool.append(StrategicPoint(_INSIGHT_GCC_GEO_TITLE, _INSIGHT_GCC_GEO_BODY))

    if not raised and revenue < 5_000_000:
        insight_pool.append(
            StrategicPoint(_INSIGHT_PRE_FUNDRAISE_TITLE, _INSIGHT_PRE_FUNDRAISE_BODY)
        )
    elif raised and re.search(r"series a|seed", stage, re.IGNORECASE) and revenue < 10_000_000:
        insight_pool.append(
            StrategicPoint(_INSIGHT_SERIES_B_READY_TITLE, _INSIGHT_SERIES_B_READY_BODY)
        )

    if signals["isB2BSector"] and revenue >= 2_000_000:
        insight_pool.append(
            StrategicPoint(_INSIGHT_B2B_NRR_TITLE, _INSIGHT_B2B_NRR_BODY.format(company=company))
        )

    if signals["isTravelLifestyle"] or signals["isFashionLifestyle"] or signals["isPersonalised"]:
        insight_pool.append(
            StrategicPoint(_INSIGHT_LIFESTYLE_DATA_TITLE, _INSIGHT_LIFESTYLE_DATA_BODY)
        )

    final_insights = insight_pool[:2]
    if len(final_insights) < 1:
        final_insights.append(
            StrategicPoint(
                _INSIGHT_FALLBACK_1_TITLE, _INSIGHT_FALLBACK_1_BODY.format(company=company)
            )
        )
    if len(final_insights) < 2:
        final_insights.append(StrategicPoint(_INSIGHT_FALLBACK_2_TITLE, _INSIGHT_FALLBACK_2_BODY))

    return StrategicAnalysisResult(
        pros=tuple(final_pros[:3]),
        cons=tuple(final_cons[:3]),
        insights=tuple(final_insights[:2]),
    )
