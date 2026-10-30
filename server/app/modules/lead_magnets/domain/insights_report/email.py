"""The one-time code email for the report gate."""

from app.modules.lead_magnets.domain.shared.email_content import (
    EmailContent,
    esc,
    render_code_shell,
)


def build_code_email(*, code: str, report_title: str, ttl_min: int) -> EmailContent:
    # One wording for both parts, so the plain-text copy can't drift from the HTML.
    note = (
        f"The code expires in {ttl_min} minutes. If you didn't ask for it, "
        "you can safely ignore this email."
    )
    return EmailContent(
        subject=f"{code} is your Wusool report code",
        html=render_code_shell(
            tag="Insights &amp; Reports",
            heading="Your verification code",
            sub=f"Enter this code to read <strong>{esc(report_title)}</strong>.",
            code=code,
            note=note,
        ),
        text=(
            f"Your verification code: {code}\n\n"
            f"Enter this code to read {report_title}.\n\n"
            f"{note}\n\n"
            "Wusool Capital - M&A Advisory, UAE & GCC\n"
        ),
    )
