"""Web-fallback result message — shown instead of the normal ranked-CRM-
candidate message when no CRM seller's score clears the qualifying
threshold. Block Kit builders only, no logic. Leads are unverified and
never persisted (§ web_search module docstring), so the message says so
plainly rather than presenting them as equivalent to a CRM match.
"""

from app.modules.web_search.domain.firecrawl_client import WebSourcedLead


def build_web_fallback_blocks(buyer_org_name: str, leads: list[WebSourcedLead]) -> list[dict]:
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Buyer:*\n{buyer_org_name}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"⚠️ No qualifying CRM sellers found — showing {len(leads)} "
                        "web-sourced lead(s). *Not yet in CRM, unverified.*"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    for rank, lead in enumerate(leads, start=1):
        detail = lead.address or lead.category or lead.snippet or "No further details available."
        text = f"*{rank}. {lead.name}*\n{detail}"
        if lead.category and lead.address:
            text = f"*{rank}. {lead.name}*\n{lead.category}\n{lead.address}"

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
                "accessory": {
                    "type": "button",
                    "action_id": "view_web_lead_source",
                    "text": {"type": "plain_text", "text": "View Source"},
                    "url": lead.source_url,
                },
            }
        )

    return blocks
