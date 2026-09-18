"""Visitor confirmation and internal-notice email content for the Get
Started tool.
"""

from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    format_count,
    format_usd,
    render_confirmation_shell,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload, GetStartedPayload
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.utilities.domain.json_types import JsonObject

# Get Started is a seller tool like valuation/readiness/benchmark, not a
# buyer one — same calendar as those three, not buyer_network's own.
_SELLER_CTA = "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"


def build_confirmation(payload: JsonObject) -> EmailContent:
    return EmailContent(
        subject="Thanks for reaching out to Wusool Capital",
        html=render_confirmation_shell(
            tag="Get Started",
            heading="We've got it.",
            sub="A member of our team will review your business and follow up within 48 hours.",
            body=(
                "Your details have been securely received. We'll review your business "
                "and reach out to discuss your priorities and the options available to you."
            ),
            cta_text="Book a Call",
            cta_href=_SELLER_CTA,
        ),
    )


def build_internal(payload: JsonObject, ai: JsonObject, subjects: SubjectRefs) -> EmailContent:
    identity = AttioIdentityPayload.model_validate(payload)
    numbers = GetStartedPayload.model_validate(payload)
    company = identity.company or payload.get("company_name") or "Unknown"

    sector = identity.sector or "—"
    sector_other = payload.get("sector_other")
    if sector_other:
        sector = f"{sector} — {sector_other}"

    rows = render_field_rows(
        [
            ("Full Name", identity.name or "—"),
            ("Email", identity.email or "—"),
            ("Business Website", identity.domain or "Not provided"),
            ("Country", identity.geography or "—"),
            ("Sector", sector),
            ("Annual Revenue", format_usd(numbers.revenue)),
            ("Annual EBITDA", format_usd(numbers.ebitda)),
            ("Years in Business", format_count(numbers.years_active)),
            ("Looking to Sell", numbers.sell_timeline or "—"),
        ]
    )

    return EmailContent(
        subject=f"New Seller Lead — {company}",
        html=render_internal_shell(
            badge="New Seller Lead",
            badge_color="#c96a3e",
            title=str(company),
            rows_html=rows,
            org_url=subjects.org_web_url,
            deal_url=subjects.deal_web_url,
        ),
    )
