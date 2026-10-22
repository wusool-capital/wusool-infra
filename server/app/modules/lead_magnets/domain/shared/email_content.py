"""Shared HTML shell + formatting for the two emails every lead-magnet
submission sends: a visitor confirmation and an internal ops notice.

Pure string building — no I/O, no pydantic. Per-tool copy and field data
live in each tool's own `domain/<tool>/email.py`; this file only owns the
shell markup common to all of them, mirrored from Wusool Capital's existing
email templates so a rendered email matches the brand exactly.
"""

import re
from dataclasses import dataclass
from html import escape
from urllib.parse import quote


@dataclass(frozen=True)
class EmailContent:
    subject: str
    html: str


# Same asset the live tool pages already embed (`static/img/a0288d00.png`),
# content-addressed and served immutably at this path in every environment
# — see `api/static.py`. Used in place of a text wordmark so the emails
# match the brand exactly.
_LOGO_URL = "https://tools.wusoolcapital.com/img/a0288d00.png"
_LOGO_IMG = (
    f'<img src="{_LOGO_URL}" width="120" height="20" alt="Wusool Capital" '
    'style="display:block;width:120px;height:20px;border:0;">'
)


# The browser's own email grammar, plus a dot in the domain, so "dana@acme" fails.
# ASCII only and no comma or newline, which blocks Reply-To header injection.
EMAIL_PATTERN = (
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_EMAIL_RE = re.compile(EMAIL_PATTERN)


def is_valid_email(value: str) -> bool:
    # `fullmatch`, not `match`: `$` alone would accept a trailing newline.
    return _EMAIL_RE.fullmatch(value) is not None


def _mailto(email: str) -> str:
    # URL-encode: the pattern allows `?`, `&` and `#`, which would add mailto headers.
    return esc(f"mailto:{quote(email, safe='@')}")


def esc(value: object) -> str:
    """Escapes a value that may carry a visitor's raw form input before it's
    interpolated into HTML — every field-table cell, free-text answer, and
    company/person name in these emails passes through here. Static,
    hand-authored copy (confirmation-email headings/body text, which already
    contains real entities like `&amp;`) never goes through this — only
    render_field_rows/render_internal_shell's `title` do, since those are
    the only two seams that ever carry submitted data."""
    return escape(str(value))


def format_usd(value: float | None) -> str:
    return f"USD {value:,.0f}" if value is not None else "-"


def format_pct(value: float | None) -> str:
    return f"{value:g}%" if value is not None else "-"


def format_count(value: float | None) -> str:
    return f"{value:g}" if value is not None else "-"


def format_consent(value: bool | None) -> str:
    return "-" if value is None else ("Yes" if value else "No")


def render_confirmation_shell(
    *, tag: str, heading: str, sub: str, body: str, cta_text: str, cta_href: str
) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f2f2f2;font-family:Inter,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f2f2f2;padding:40px 20px;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e5e5e5;">
<tr><td style="padding:28px 36px;border-bottom:1px solid #eeeeee;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td>{_LOGO_IMG}</td>
<td align="right"><span style="font-family:Inter,sans-serif;font-size:11px;color:#999999;letter-spacing:0.5px;">{tag}</span></td>
</tr></table></td></tr>
<tr><td style="padding:36px 36px 28px 36px;">
<p style="font-family:Inter,sans-serif;font-size:22px;font-weight:700;color:#000000;margin:0 0 6px 0;line-height:1.3;">{heading}</p>
<p style="font-family:Inter,sans-serif;font-size:14px;color:#666666;margin:0 0 28px 0;">{sub}</p>
<p style="font-family:Inter,sans-serif;font-size:14px;color:#333333;line-height:1.8;margin:0 0 32px 0;">{body}</p>
<p style="font-family:Inter,sans-serif;font-size:13px;color:#666666;margin:0 0 14px 0;">Prefer to schedule a call now?</p>
<a href="{cta_href}" style="display:inline-block;background-color:#000000;color:#ffffff;font-family:Inter,sans-serif;font-size:13px;font-weight:700;text-decoration:none;padding:12px 24px;border-radius:6px;">{cta_text}</a>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #eeeeee;background-color:#fafafa;">
<p style="font-family:Inter,sans-serif;font-size:12px;color:#999999;margin:0;">Wusool Capital - M&amp;A Advisory, UAE &amp; GCC</p>
</td></tr></table></td></tr></table></body></html>"""


def render_code_shell(*, tag: str, heading: str, sub: str, code: str, note: str) -> str:
    """The confirmation shell's frame around a one-time code instead of a CTA."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f2f2f2;font-family:Inter,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f2f2f2;padding:40px 20px;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e5e5e5;">
<tr><td style="padding:28px 36px;border-bottom:1px solid #eeeeee;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td>{_LOGO_IMG}</td>
<td align="right"><span style="font-family:Inter,sans-serif;font-size:11px;color:#999999;letter-spacing:0.5px;">{tag}</span></td>
</tr></table></td></tr>
<tr><td style="padding:36px 36px 28px 36px;">
<p style="font-family:Inter,sans-serif;font-size:22px;font-weight:700;color:#000000;margin:0 0 6px 0;line-height:1.3;">{heading}</p>
<p style="font-family:Inter,sans-serif;font-size:14px;color:#666666;margin:0 0 28px 0;">{sub}</p>
<table cellpadding="0" cellspacing="0" style="margin:0 0 28px 0;"><tr>
<td style="background-color:#f5f5f5;border:1px solid #e5e5e5;border-radius:8px;padding:16px 28px;font-family:'Courier New',monospace;font-size:32px;font-weight:700;letter-spacing:10px;color:#000000;">{code}</td>
</tr></table>
<p style="font-family:Inter,sans-serif;font-size:13px;color:#666666;line-height:1.7;margin:0;">{note}</p>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #eeeeee;background-color:#fafafa;">
<p style="font-family:Inter,sans-serif;font-size:12px;color:#999999;margin:0;">Wusool Capital - M&amp;A Advisory, UAE &amp; GCC</p>
</td></tr></table></td></tr></table></body></html>"""


def render_field_rows(pairs: list[tuple[str, str]]) -> str:
    last = len(pairs) - 1
    rows = []
    for i, (label, value) in enumerate(pairs):
        border = "" if i == last else "border-bottom:1px solid #f5f5f5;"
        rows.append(
            f'<tr><td style="padding:10px 14px;color:#666666;vertical-align:top;{border}">{esc(label)}</td>'
            f'<td style="padding:10px 14px;color:#000000;font-weight:600;{border}">{esc(value)}</td></tr>'
        )
    return "".join(rows)


def _link_button(text: str, href: str, *, filled: bool) -> str:
    if filled:
        style = (
            "display:inline-block;background-color:#000000;color:#ffffff;"
            "font-family:Arial,sans-serif;font-size:13px;font-weight:700;"
            "text-decoration:none;padding:11px 22px;border-radius:6px;"
        )
    else:
        style = (
            "display:inline-block;background-color:#ffffff;color:#000000;"
            "font-family:Arial,sans-serif;font-size:13px;font-weight:700;"
            "text-decoration:none;padding:10px 21px;border-radius:6px;border:1px solid #000000;"
        )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">'
        f'<tr><td><a href="{href}" style="{style}">{text}</a></td></tr></table>'
    )


def _lead_rows(name: str, email: str) -> str:
    """Name, then Email: a `mailto:` link when valid, a warning chip when not."""
    name_row = render_field_rows([("Full Name", name or "-")])
    cell = "padding:10px 14px;border-bottom:1px solid #f5f5f5;"
    if is_valid_email(email):
        value = (
            f'<a href="{_mailto(email)}" style="color:#1a56b8;text-decoration:underline;">'
            f"{esc(email)}</a>"
        )
        value_style = f"{cell}font-weight:600;"
    else:
        value = (
            f"{esc(email or '-')}"
            '<span style="display:inline-block;margin-left:6px;background-color:#fbe9dc;'
            "color:#a3531f;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;"
            '">&#9888;&#65039; Invalid email</span>'
        )
        value_style = f"{cell}color:#000000;font-weight:600;"
    return (
        f"{name_row}"
        f'<tr><td style="{cell}color:#666666;vertical-align:top;">Email</td>'
        f'<td style="{value_style}">{value}</td></tr>'
    )


def render_internal_shell(
    *,
    badge: str,
    badge_color: str,
    title: str,
    lead_name: str,
    lead_email: str,
    rows_html: str,
    org_url: str | None,
    deal_url: str | None,
    extra_html: str = "",
) -> str:
    """`org_url`/`deal_url` are `None` whenever Attio's response omitted
    `web_url` (or the org write hit the dedup/patch path) — the
    corresponding button is simply left out rather than linking nowhere.

    Name and Email lead the table, so `rows_html` carries only the other
    fields. The Reply button exists only for a valid address.
    """
    valid = is_valid_email(lead_email)
    first_name = (lead_name.split() or ["lead"])[0]
    buttons = "".join(
        [
            _link_button(f"Reply to {esc(first_name)}", _mailto(lead_email), filled=True)
            if valid
            else "",
            _link_button("View Organisation", org_url, filled=not valid) if org_url else "",
            _link_button("View Deal", deal_url, filled=False) if deal_url else "",
        ]
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#f2f2f2;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f2f2f2;padding:32px 16px;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e5e5e5;">
<tr><td style="padding:24px 32px;border-bottom:1px solid #eeeeee;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td>{_LOGO_IMG}</td>
<td align="right"><span style="background-color:{badge_color};color:#ffffff;font-family:Arial,sans-serif;font-size:10px;font-weight:700;padding:3px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:0.5px;">{badge}</span></td>
</tr></table></td></tr>
<tr><td style="padding:28px 32px 8px 32px;">
<p style="font-family:Arial,sans-serif;font-size:18px;font-weight:700;color:#000000;margin:0 0 4px 0;">{esc(title)}</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eeeeee;border-radius:6px;font-family:Arial,sans-serif;font-size:13px;">
{_lead_rows(lead_name, lead_email)}{rows_html}
</table>
{extra_html}
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;margin-bottom:16px;"><tr><td>
{buttons}
</td></tr></table>
</td></tr>
<tr><td style="padding:16px 32px;border-top:1px solid #eeeeee;background-color:#fafafa;">
<p style="font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;margin:0;">Wusool Capital - wusoolcapital.com</p>
</td></tr></table></td></tr></table></body></html>"""
