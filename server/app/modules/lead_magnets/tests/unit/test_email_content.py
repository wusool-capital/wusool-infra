"""Shared email-rendering primitives: HTML escaping is the load-bearing
behaviour here — every value comes from a visitor's own form input.
"""

import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from app.modules.lead_magnets.application.shared.email_dispatch import (
    build_confirmation_email,
    build_internal_email,
)
from app.modules.lead_magnets.domain.shared.email_content import (
    ReplyDraft,
    is_valid_email,
    render_field_rows,
    render_internal_shell,
)
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

_REPLY = ReplyDraft(
    confirmation_subject="Your request is in",
    thank_you="Thank you.",
    purpose="talk",
    booking_url="https://calendar.example/book",
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
        lead_name="Dana Lee",
        lead_email="dana@acme.com",
        reply=_REPLY,
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
        lead_name="Dana Lee",
        lead_email="dana@acme.com",
        reply=_REPLY,
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
        lead_name="Dana Lee",
        lead_email="dana@acme.com",
        reply=_REPLY,
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
    assert "Other - pool maintenance" in content.html


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


@pytest.mark.parametrize(
    "tool", ["benchmark", "buyer_network", "get_started", "readiness", "valuation"]
)
def test_the_book_call_button_goes_through_the_tracked_redirect(tool: str) -> None:
    from app.modules.lead_magnets.application.shared.email_dispatch import (
        build_confirmation_email,
    )

    html = build_confirmation_email(
        tool, {"submission_id": "abc 123"}, "https://tools.example.com/"
    ).html

    assert f'href="https://tools.example.com/go/book-call/{tool}?sid=abc%20123"' in html
    assert "calendar.app.google" not in html, "the calendar is only known to the server"


@pytest.mark.parametrize(
    ("tool", "calendar"),
    [
        ("valuation", "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"),
        ("buyer_network", "https://calendar.app.google/4FzN5jAf5KGQszjY7"),
    ],
)
def test_with_no_base_url_the_button_keeps_the_direct_calendar_link(
    tool: str, calendar: str
) -> None:
    from app.modules.lead_magnets.application.shared.email_dispatch import (
        build_confirmation_email,
    )

    assert f'href="{calendar}"' in build_confirmation_email(tool, {"submission_id": "x"}).html


def test_the_tracked_link_never_carries_an_email_or_a_url() -> None:
    from app.modules.lead_magnets.domain.shared.book_call import book_call_href

    href = book_call_href("https://tools.example.com", "readiness", "a&b=c/d")

    assert href == "https://tools.example.com/go/book-call/readiness?sid=a%26b%3Dc%2Fd"


_SUBJECTS = SubjectRefs(
    org_web_url="https://app.attio.com/org/1", deal_web_url="https://app.attio.com/deal/1"
)

_IDENTITY = {
    "name": "Dana Lee",
    "company": "Acme Trading",
    "email": "dana@acme.com",
    "domain": "acme.com",
}

_PAYLOADS = {
    "valuation": {**_IDENTITY, "description": "Distributor", "revenue": 5_000_000, "consent": True},
    "readiness": {**_IDENTITY, "answers": {}},
    "benchmark": {**_IDENTITY, "peer_key": "retail", "phone": "+971500000000", "consent": True},
    "buyer_network": {
        "full_name": "Priya Nair",
        "org_name": "Fictive Capital",
        "email": "priya@fictive.com",
        "domain": "fictive.com",
        "consent": True,
    },
    "get_started": {**_IDENTITY, "years_active": 3, "sell_timeline": "Immediate", "consent": True},
}


def _internal(tool: str, **overrides: object) -> tuple[str, str]:
    content = build_internal_email(tool, {**_PAYLOADS[tool], **overrides}, {}, _SUBJECTS)
    return content.subject, content.html


@pytest.mark.parametrize(
    ("tool", "subject"),
    [
        ("valuation", "New Seller Lead - Acme Trading"),
        ("readiness", "New Seller Lead - Acme Trading"),
        ("benchmark", "New Seller Lead - Acme Trading"),
        ("get_started", "New Seller Lead - Acme Trading"),
        ("buyer_network", "New Buyer Lead - Priya Nair"),
    ],
)
def test_internal_subjects(tool: str, subject: str) -> None:
    assert _internal(tool)[0] == subject


@pytest.mark.parametrize("tool", list(_PAYLOADS))
def test_valid_email_gets_mailto_and_reply_button(tool: str) -> None:
    html = _internal(tool)[1]
    email = _PAYLOADS[tool]["email"]
    assert f'href="mailto:{email}"' in html
    first = str(_PAYLOADS[tool].get("name") or _PAYLOADS[tool].get("full_name")).split()[0]
    assert f"Reply to {first}" in html
    assert "Invalid email" not in html


@pytest.mark.parametrize("tool", list(_PAYLOADS))
def test_invalid_email_shows_warning_and_no_reply_button(tool: str) -> None:
    html = _internal(tool, email="abc")[1]
    assert "mailto:" not in html
    assert "Reply to" not in html
    assert "Invalid email" in html
    assert "abc" in html


def test_reply_button_escapes_the_first_name() -> None:
    html = _internal("valuation", name="<b>Dana")[1]
    assert "<b>Dana" not in html
    assert "Reply to &lt;b&gt;Dana" in html


def test_missing_name_falls_back_to_lead() -> None:
    assert "Reply to lead" in _internal("valuation", name="")[1]


def test_valuation_lists_every_form_field() -> None:
    html = _internal("valuation")[1]
    for label in (
        "Company",
        "Website",
        "Description",
        "Revenue at Last Raise",
        "PBT at Last Raise",
        "Cash",
        "Debt",
        "Consent",
    ):
        assert f">{label}</td>" in html


def test_benchmark_and_buyer_list_every_form_field() -> None:
    benchmark = _internal("benchmark")[1]
    for label in (
        "Phone",
        "Website",
        "Geography",
        "Salary Deducted in EBITDA",
        "Rent Cost",
        "Capital Raised",
        "Outlets",
        "Consent",
    ):
        assert f">{label}</td>" in benchmark
    buyer = _internal("buyer_network")[1]
    for label in ("Organisation", "Website", "Consent"):
        assert f">{label}</td>" in buyer


@pytest.mark.parametrize("tool", list(_PAYLOADS))
def test_no_em_dash_in_any_lead_magnet_email(tool: str) -> None:
    rendered = [
        _internal(tool)[0],
        _internal(tool)[1],
        _internal(tool, email="abc")[1],
        build_confirmation_email(tool, _PAYLOADS[tool]).subject,
        build_confirmation_email(tool, _PAYLOADS[tool]).html,
    ]
    for text in rendered:
        assert "—" not in text
        assert "&mdash;" not in text
        assert "&#8212;" not in text


def test_readiness_scored_answers_have_no_em_dash() -> None:
    answers = {"q1": 3, "q4": 2, "q6": 3}
    html = _internal("readiness", answers=answers)[1]
    assert "—" not in html


@pytest.mark.parametrize("value", ["dana@acme.com", "a.b+c@sub.acme.co", "o'neil@acme.com"])
def test_is_valid_email_accepts(value: str) -> None:
    assert is_valid_email(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "dana@acme",
        "a@b.co\n",
        "a@b.co\r\nBcc: x@y.z",
        "a@b.co,c@d.eu",
        "dänä@acme.com",
        "a b@acme.com",
    ],
)
def test_is_valid_email_rejects(value: str) -> None:
    assert not is_valid_email(value)


def test_mailto_links_url_encode_the_address() -> None:
    html = _internal("valuation", email="a?cc=x@acme.com")[1]
    assert "mailto:a%3Fcc%3Dx@acme.com" in html
    assert "mailto:a?cc" not in html


_REPLY_SUBJECTS = {
    "valuation": "Re: Your valuation request is in",
    "readiness": "Re: Your M&A readiness assessment is complete",
    "benchmark": "Re: Your GCC SME benchmark report is ready",
    "get_started": "Re: Thanks for reaching out to Wusool Capital",
    "buyer_network": "Re: Application received",
}


def _reply_query(tool: str, **overrides: object) -> dict[str, list[str]]:
    html = _internal(tool, **overrides)[1]
    href = re.search(r'href="(mailto:[^"]*\?[^"]*)"', html)
    assert href, "no Reply button with a draft"
    return parse_qs(urlsplit(href.group(1).replace("&amp;", "&")).query)


@pytest.mark.parametrize("tool", list(_PAYLOADS))
def test_reply_button_prefills_a_call_scheduling_draft(tool: str) -> None:
    query = _reply_query(tool)
    first = str(_PAYLOADS[tool].get("name") or _PAYLOADS[tool].get("full_name")).split()[0]
    body = query["body"][0]
    assert query["subject"] == [_REPLY_SUBJECTS[tool]]
    assert body.startswith(f"Hi {first},\n\n")
    assert "I'd welcome a short call to" in body
    assert "https://calendar.app.google/" in body
    assert "reply with a few times that work for you" in body
    assert body.endswith("Warm regards,\nThe Wusool Capital team")
    assert "—" not in body


def test_reply_draft_links_the_buyer_calendar_for_buyers_only() -> None:
    assert "4FzN5jAf5KGQszjY7" in _reply_query("buyer_network")["body"][0]
    for tool in ("valuation", "readiness", "benchmark", "get_started"):
        assert "UfXxu6dBkZ8wjhnT6" in _reply_query(tool)["body"][0]


def test_reply_draft_survives_special_characters_in_the_address_and_name() -> None:
    html = _internal("valuation", email="a?cc=x@acme.com", name="D&na")[1]
    href = re.search(r'href="(mailto:[^"]*)"', html)
    assert href
    raw = unquote(href.group(1).split("?", 1)[0])
    assert raw == "mailto:a?cc=x@acme.com"
    assert "Reply to D&amp;na" in html
    body = _reply_query("valuation", email="a?cc=x@acme.com", name="D&na")["body"][0]
    assert body.startswith("Hi D&na,")


def test_reply_draft_without_a_name_drops_the_first_name() -> None:
    body = _reply_query("valuation", name="")["body"][0]
    assert body.startswith("Hi,\n\n")
