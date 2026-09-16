"""Visitor confirmation and internal-notice email content for the
valuation tool.
"""

from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    format_usd,
    render_confirmation_shell,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload, ValuationPayload
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.utilities.domain.json_types import JsonObject

_SELLER_CTA = "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"


def build_confirmation(payload: JsonObject) -> EmailContent:
    return EmailContent(
        subject="Your valuation request is in",
        html=render_confirmation_shell(
            tag="Valuation",
            heading="Your valuation request is in.",
            sub="We're preparing your indicative range and will follow up within 48 hours.",
            body=(
                "Your company figures have been securely received. We'll benchmark them "
                "against recent comparable transactions in your sector and come back to "
                "you with an indicative valuation range and the assumptions behind it."
            ),
            cta_text="Book a Call",
            cta_href=_SELLER_CTA,
        ),
    )


def build_internal(payload: JsonObject, ai: JsonObject, subjects: SubjectRefs) -> EmailContent:
    identity = AttioIdentityPayload.model_validate(payload)
    numbers = ValuationPayload.model_validate(payload)
    # Same fallback bootstrap.py's own Attio write already uses — no real
    # request sends `company_name`, kept only for parity with that path.
    company = identity.company or payload.get("company_name") or "Unknown"

    rows = render_field_rows(
        [
            ("Full Name", identity.name or "—"),
            ("Email", identity.email or "—"),
            ("Sector", identity.sector or identity.peer_key or "—"),
            ("Geography", identity.geography or identity.country or "—"),
            ("Revenue", format_usd(numbers.revenue)),
            ("Profit Before Tax", format_usd(numbers.profit_before_tax)),
            ("Owner Salary Add-back", format_usd(numbers.owner_salary)),
            ("Stage", numbers.stage or "—"),
        ]
    )

    extra = ""
    low, mid, high = ai.get("low"), ai.get("mid"), ai.get("high")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        mid_text = f" <span style=\"font-weight:400;color:#666666;font-size:12px;\">(mid {format_usd(mid)})</span>"
        extra = (
            '<table width="100%" cellpadding="0" cellspacing="0" '
            'style="margin-top:16px;background-color:#f6f4ef;border-radius:6px;">'
            '<tr><td style="padding:12px 14px;font-family:Arial,sans-serif;font-size:12px;'
            'color:#8a6a2e;text-transform:uppercase;letter-spacing:0.5px;font-weight:700;">'
            "Indicative valuation (AI)</td></tr>"
            '<tr><td style="padding:0 14px 14px;font-family:Arial,sans-serif;font-size:16px;'
            f'color:#000000;font-weight:700;">{format_usd(low)} – {format_usd(high)}{mid_text}'
            "</td></tr></table>"
        )

    return EmailContent(
        subject=f"New Valuation — {company}",
        html=render_internal_shell(
            badge="New Valuation",
            badge_color="#b8863f",
            title=str(company),
            rows_html=rows,
            extra_html=extra,
            org_url=subjects.org_web_url,
            deal_url=subjects.deal_web_url,
        ),
    )
