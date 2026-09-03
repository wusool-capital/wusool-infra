"""Sanitization for free-form text embedded in Slack `mrkdwn` blocks."""

import re

_MARKDOWN_HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+")


def sanitize_mrkdwn(text: str) -> str:
    """Normalize unsupported Markdown without disturbing readable content.

    Slack uses tildes for strikethrough and does not render Markdown headings,
    so replace approximation tildes and remove heading markers at line starts.
    """
    normalized = _MARKDOWN_HEADING_RE.sub("", text.replace("~", "≈"))
    return normalized.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
