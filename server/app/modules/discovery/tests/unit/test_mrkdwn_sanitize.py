"""Slack's mrkdwn parses a stray Markdown heading as literal `#` text; sanitizing
must strip the marker without mangling the rest of the line. Regression moved
here from the lead-card tests, which exercised it through scraped addresses.
"""

from app.modules.notifications import sanitize_mrkdwn


def test_markdown_heading_markers_are_stripped() -> None:
    scraped = (
        "## Related content\n"
        "###### About PRI\n"
        "Set up with the UN's support.\n\n"
        "###### Become a signatory\n"
        "Demonstrate your commitment to responsible investment."
    )

    assert sanitize_mrkdwn(scraped) == (
        "Related content\n"
        "About PRI\n"
        "Set up with the UN's support.\n\n"
        "Become a signatory\n"
        "Demonstrate your commitment to responsible investment."
    )
