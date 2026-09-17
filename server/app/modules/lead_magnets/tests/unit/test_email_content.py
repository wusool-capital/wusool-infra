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
