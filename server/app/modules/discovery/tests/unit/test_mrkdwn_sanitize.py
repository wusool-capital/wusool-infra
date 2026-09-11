"""Regression coverage moved from `matching_engine` alongside
`WebSourcedLead`/`build_web_fallback_blocks` — see this module's own
`build_lead_blocks`/`DiscoveredLead`. Slack's mrkdwn parses a stray Markdown
heading as literal `#` text; sanitizing must strip the marker without
mangling the rest of the line.
"""

from app.modules.discovery.api.slack.views import build_lead_blocks
from app.modules.discovery.domain.leads import DiscoveredLead


def test_lead_details_render_without_markdown_heading_markers() -> None:
    lead = DiscoveredLead(
        name="What are the Principles | PRI",
        source_url="https://www.google.com/maps/place/What+are+the+Principles/data=!4m7",
        address=(
            "## Related content\n"
            "###### About PRI\n"
            "Set up with the UN's support.\n\n"
            "###### Become a signatory\n"
            "Demonstrate your commitment to responsible investment."
        ),
    )

    blocks = build_lead_blocks([lead])
    rendered = blocks[2].to_dict()["text"]["text"]

    assert rendered == (
        "*1. What are the Principles | PRI*\n"
        "Related content\n"
        "About PRI\n"
        "Set up with the UN's support.\n\n"
        "Become a signatory\n"
        "Demonstrate your commitment to responsible investment."
    )
