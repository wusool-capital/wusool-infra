"""Visitor confirmation and internal-notice email content for the GCC SME
benchmark tool.
"""

from app.modules.lead_magnets.domain.shared.book_call import calendar_url
from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    ReplyDraft,
    format_consent,
    format_count,
    format_pct,
    format_usd,
    render_confirmation_shell,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload, BenchmarkPayload
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.utilities.domain.json_types import JsonObject

_CONFIRMATION_SUBJECT = "Your GCC SME benchmark report is ready"
_REPLY = ReplyDraft(
    confirmation_subject=_CONFIRMATION_SUBJECT,
    thank_you="Thank you for using the GCC SME benchmark from Wusool Capital.",
    purpose="walk through where your business stands against its peers",
    booking_url=calendar_url("benchmark"),
)


def build_confirmation(payload: JsonObject, cta_href: str) -> EmailContent:
    return EmailContent(
        subject=_CONFIRMATION_SUBJECT,
        html=render_confirmation_shell(
            tag="GCC SME Benchmark",
            heading="Your benchmark report is ready.",
            sub="We'll be in touch within 48 hours to walk through where you stand.",
            body=(
                "Your figures have been benchmarked against peer businesses in your "
                "sector across the GCC - covering growth, margin, customer "
                "concentration and more. A member of our team will review your "
                "percentile scores and reach out to discuss what they mean for your "
                "business."
            ),
            cta_text="Book a Call",
            cta_href=cta_href,
        ),
    )


def build_internal(payload: JsonObject, ai: JsonObject, subjects: SubjectRefs) -> EmailContent:
    identity = AttioIdentityPayload.model_validate(payload)
    numbers = BenchmarkPayload.model_validate(payload)
    company = identity.company or payload.get("company_name") or "Unknown"

    rows = render_field_rows(
        [
            ("Phone", identity.phone or "-"),
            ("Website", identity.domain or "-"),
            ("Geography", numbers.geography or identity.geography or identity.country or "-"),
            ("Mode / Peer Group", f"{numbers.mode} - {identity.sector or numbers.peer_key or '-'}"),
            ("Revenue (this year)", format_usd(numbers.revenue)),
            ("Revenue (prior year)", format_usd(numbers.prev_revenue)),
            ("EBITDA (reported)", format_usd(numbers.ebitda_reported)),
            ("Owner Salary", format_usd(numbers.owner_salary)),
            ("Salary Deducted in EBITDA", "Yes" if numbers.salary_deducted else "No"),
            ("Gross Margin", format_pct(numbers.gross_margin_pct)),
            ("Headcount", format_count(numbers.headcount)),
            ("Rent Cost", format_usd(numbers.rent_cost)),
            ("Capital Raised", format_usd(numbers.capital_raised)),
            ("Outlets", format_count(numbers.outlets)),
            ("Recurring Revenue", format_pct(numbers.recurring_pct)),
            ("Top Customer Share", format_pct(numbers.top_customer_pct)),
            ("Years Active", format_count(numbers.years_active)),
            ("Days to Get Paid", format_count(numbers.days_to_get_paid)),
            ("Consent", format_consent(numbers.consent)),
        ]
    )

    entry_values_raw = ai.get("entry_values")
    entry_values: dict[str, object] = entry_values_raw if isinstance(entry_values_raw, dict) else {}
    score, band = ai.get("score"), ai.get("band")
    quartile = entry_values.get("benchmark_quartile")
    extra = ""
    if isinstance(score, (int, float)):
        detail = " &middot; ".join(str(x) for x in (band, quartile) if x)
        detail_html = (
            f' <span style="font-weight:400;color:#666666;font-size:12px;">{detail}</span>'
            if detail
            else ""
        )
        extra = (
            '<table width="100%" cellpadding="0" cellspacing="0" '
            'style="margin-top:16px;background-color:#f6f2fb;border-radius:6px;">'
            '<tr><td style="padding:12px 14px;font-family:Arial,sans-serif;font-size:12px;'
            'color:#6b3fa0;text-transform:uppercase;letter-spacing:0.5px;font-weight:700;">'
            "Benchmark result</td></tr>"
            f'<tr><td style="padding:0 14px 14px;font-family:Arial,sans-serif;font-size:16px;'
            f'color:#000000;font-weight:700;">Score {score:g}{detail_html}</td></tr></table>'
        )

    return EmailContent(
        subject=f"New Seller Lead - {company}",
        html=render_internal_shell(
            badge="New Benchmark",
            badge_color="#8a5fc2",
            title=str(company),
            lead_name=identity.name,
            reply=_REPLY,
            lead_email=identity.email,
            rows_html=rows,
            extra_html=extra,
            org_url=subjects.org_web_url,
            deal_url=subjects.deal_web_url,
        ),
    )
