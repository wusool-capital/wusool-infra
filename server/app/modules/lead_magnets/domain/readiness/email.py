"""Visitor confirmation and internal-notice email content for the M&A
readiness tool.
"""

from app.modules.lead_magnets.domain.readiness.readiness import ReadinessAnswers
from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    esc,
    render_confirmation_shell,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload, ReadinessPayload
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.utilities.domain.json_types import JsonObject

_SELLER_CTA = "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"


def build_confirmation(payload: JsonObject) -> EmailContent:
    return EmailContent(
        subject="Your M&A readiness assessment is complete",
        html=render_confirmation_shell(
            tag="M&amp;A Readiness",
            heading="Your readiness assessment is complete.",
            sub="A member of our team will review your results and follow up within 48 hours.",
            body=(
                "Your answers have been scored against our 13-point M&amp;A readiness "
                "framework, covering financial hygiene, customer concentration, "
                "management depth and legal standing. We'll review your report and reach "
                "out to discuss how to close any gaps before a sale process."
            ),
            cta_text="Book a Call",
            cta_href=_SELLER_CTA,
        ),
    )


def build_internal(payload: JsonObject, ai: JsonObject, subjects: SubjectRefs) -> EmailContent:
    identity = AttioIdentityPayload.model_validate(payload)
    parsed = ReadinessPayload.model_validate(payload)
    answers = ReadinessAnswers(**parsed.answers.model_dump())
    company = identity.company or parsed.company or "Unknown"

    score_raw = ai.get("score")
    score: dict[str, object] = score_raw if isinstance(score_raw, dict) else {}
    overall_score = score.get("overallScore")
    score_band = score.get("scoreBand")
    score_text = (
        f"{overall_score:g} / 100" if isinstance(overall_score, (int, float)) else "—"
    )
    score_band_text = str(score_band) if isinstance(score_band, str) and score_band else "—"

    rows = render_field_rows(
        [
            ("Full Name", identity.name or parsed.name or "—"),
            ("Email", identity.email or "—"),
            ("Sector", identity.sector or parsed.sector or "—"),
            ("Country", identity.country or parsed.country or "—"),
            ("Est. Revenue", parsed.revenue or "—"),
            ("Readiness Score", score_text),
            ("Readiness Band", score_band_text),
        ]
    )

    scored_rows = render_field_rows(answers.scored_labels())
    free_text_fields = (("Biggest concern", answers.q14), ("What would help most", answers.q15))
    free_text = "".join(
        f'<tr><td colspan="2" style="padding:10px 14px 0;color:#666666;">{esc(label)}</td></tr>'
        f'<tr><td colspan="2" style="padding:0 14px 12px;color:#000000;">"{esc(value)}"</td></tr>'
        for label, value in free_text_fields
        if value
    )
    extra = (
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;border:1px solid #eeeeee;border-radius:6px;'
        'font-family:Arial,sans-serif;font-size:12.5px;">'
        '<tr><td colspan="2" style="padding:9px 14px;background-color:#f7f8fb;color:#3f6fb8;'
        'font-weight:700;text-transform:uppercase;letter-spacing:0.4px;font-size:11px;">'
        "Scored answers</td></tr>"
        f"{scored_rows}{free_text}"
        "</table>"
    )

    return EmailContent(
        subject=f"New Readiness — {company}",
        html=render_internal_shell(
            badge="New Readiness",
            badge_color="#3f6fb8",
            title=str(company),
            rows_html=rows,
            extra_html=extra,
            org_url=subjects.org_web_url,
            deal_url=subjects.deal_web_url,
        ),
    )
