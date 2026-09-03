"""Generic text-sanitization helpers with no Slack- or module-specific
behavior of their own beyond the vendor format they target."""

import re

_MARKDOWN_HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+")


def sanitize_mrkdwn(text: str) -> str:
    """Normalize unsupported Markdown for embedding in a Slack `mrkdwn` block.

    Slack uses tildes for strikethrough and does not render Markdown headings,
    so replace approximation tildes and remove heading markers at line starts.
    Also escapes `&`/`<`/`>`, since Slack's `mrkdwn` reserves them for its own
    entity/link syntax the way HTML does.
    """
    normalized = _MARKDOWN_HEADING_RE.sub("", text.replace("~", "≈"))
    return normalized.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
