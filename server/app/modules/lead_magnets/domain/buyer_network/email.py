"""Visitor confirmation and internal-notice email content for the buyer
network tool.
"""

from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    format_usd,
    render_confirmation_shell,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.schemas import BuyerNetworkPayload
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.utilities.domain.json_types import JsonObject

_BUYER_CTA = "https://calendar.app.google/4FzN5jAf5KGQszjY7"


def build_confirmation(payload: JsonObject) -> EmailContent:
    return EmailContent(
        subject="Application received",
        html=render_confirmation_shell(
            tag="Buyer Network",
            heading="Application received.",
            sub="We review every application personally and will be in touch within 48 hours.",
            body=(
                "Your details have been added to our internal database. A member of "
                "the Wusool Capital team will reach out shortly to understand your "
                "acquisition priorities and align on deal criteria."
            ),
            cta_text="Book a Call",
            cta_href=_BUYER_CTA,
        ),
    )


def build_internal(payload: JsonObject, ai: JsonObject, subjects: SubjectRefs) -> EmailContent:
    buyer = BuyerNetworkPayload.model_validate(payload)
    company = buyer.org_name or "Unknown"

    check_size = "–".join(
        format_usd(v) for v in (buyer.check_size_min, buyer.check_size_max) if v is not None
    ) or "—"

    rows = render_field_rows(
        [
            ("Full Name", buyer.full_name or "—"),
            ("Email", buyer.email or "—"),
            ("Org Type", ", ".join(buyer.org_type) or "—"),
            ("Geo Focus", ", ".join(buyer.target_geography) or "—"),
            ("Sectors", ", ".join(buyer.sector_focus) or "—"),
            ("Check Size", check_size),
            ("Prior GCC Deal", buyer.prior_gcc_acquisition or "—"),
            ("LinkedIn", buyer.linkedin_url or "Not provided"),
        ]
    )

    return EmailContent(
        subject=f"New Buyer — {company}",
        html=render_internal_shell(
            badge="New Buyer",
            badge_color="#1f9d6c",
            title=str(company),
            rows_html=rows,
            org_url=subjects.org_web_url,
            deal_url=subjects.deal_web_url,
        ),
    )
