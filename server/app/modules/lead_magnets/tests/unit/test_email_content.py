"""Shared email-rendering primitives: HTML escaping is the load-bearing
behaviour here — every value comes from a visitor's own form input.
"""

from app.modules.lead_magnets.domain.shared.email_content import (
    render_field_rows,
    render_internal_shell,
)


def test_field_row_values_are_escaped() -> None:
    html = render_field_rows([("Note", "<img src=x onerror=alert(1)>")])
    assert "<img" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_field_row_labels_are_escaped() -> None:
    html = render_field_rows([("<script>", "value")])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_internal_shell_title_is_escaped() -> None:
    html = render_internal_shell(
        badge="New Lead",
        badge_color="#000000",
        title="<script>alert(1)</script> Co",
        rows_html="",
        org_url=None,
        deal_url=None,
    )
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; Co" in html


def test_internal_shell_omits_buttons_without_urls() -> None:
    html = render_internal_shell(
        badge="New Lead",
        badge_color="#000000",
        title="Acme",
        rows_html="",
        org_url=None,
        deal_url=None,
    )
    assert "View Organisation" not in html
    assert "View Deal" not in html


def test_internal_shell_includes_only_the_urls_given() -> None:
    html = render_internal_shell(
        badge="New Lead",
        badge_color="#000000",
        title="Acme",
        rows_html="",
        org_url="https://app.attio.com/org/1",
        deal_url=None,
    )
    assert "View Organisation" in html
    assert "https://app.attio.com/org/1" in html
    assert "View Deal" not in html


def test_get_started_dispatches_through_email_dispatch() -> None:
    """The actual gap this closes: `get_started` was missing from
    `email_dispatch.py`'s `_BUILDERS`, so any real submission with an email
    address would `KeyError` inside `_ensure_email_confirmation`, get caught
    and marked "failed", and never reach the internal notice either."""
    from app.modules.lead_magnets.application.shared.email_dispatch import (
        build_confirmation_email,
        build_internal_email,
    )
    from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

    payload = {
        "name": "Dana",
        "company": "Acme Trading",
        "email": "dana@acme.com",
        "domain": "acme.com",
        "geography": "UAE",
        "sector": "Logistics",
        "revenue": 3_268_209,
        "ebitda": 653_641,
        "years_active": 8,
        "sell_timeline": "Within 6 Months",
    }

    confirmation = build_confirmation_email("get_started", payload)
    assert confirmation.subject
    assert confirmation.html

    internal = build_internal_email(
        "get_started",
        payload,
        {},
        SubjectRefs(
            org_web_url="https://app.attio.com/org/1", deal_web_url="https://app.attio.com/deal/1"
        ),
    )
    assert "Acme Trading" in internal.html
    assert "dana@acme.com" in internal.html
    assert "Within 6 Months" in internal.html
    assert "View Organisation" in internal.html
    assert "View Deal" in internal.html


def test_get_started_internal_email_shows_the_self_described_sector() -> None:
    from app.modules.lead_magnets.domain.get_started.email import build_internal
    from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

    content = build_internal(
        {
            "company": "Acme",
            "sector": "Other",
            "sector_other": "pool maintenance",
            "years_active": 8,
            "sell_timeline": "Immediate",
        },
        {},
        SubjectRefs(),
    )
    assert "Other — pool maintenance" in content.html


def test_get_started_internal_email_escapes_the_self_described_sector() -> None:
    """The XSS gap code review already caught once in the other four
    tools' emails — pinning it here so it isn't reintroduced by the one
    field this tool alone has that they don't."""
    from app.modules.lead_magnets.domain.get_started.email import build_internal
    from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

    content = build_internal(
        {
            "company": "Acme",
            "sector": "Other",
            "sector_other": "<img src=x onerror=alert(1)>",
            "years_active": 8,
            "sell_timeline": "Immediate",
        },
        {},
        SubjectRefs(),
    )
    # Not a bare "<img" absence check: the shell's own logo is a legitimate
    # <img> tag. The payload's exact unescaped form must not survive.
    assert "<img src=x onerror=alert(1)>" not in content.html
    assert "&lt;img src=x onerror=alert(1)&gt;" in content.html


def test_get_started_internal_email_omits_missing_domain() -> None:
    from app.modules.lead_magnets.domain.get_started.email import build_internal
    from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

    content = build_internal(
        {"company": "Acme", "years_active": 3, "sell_timeline": "Not Selling"}, {}, SubjectRefs()
    )
    assert "Not provided" in content.html
