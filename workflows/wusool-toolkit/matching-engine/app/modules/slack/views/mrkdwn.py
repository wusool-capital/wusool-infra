"""Sanitization for free-form/LLM-generated text embedded in Slack `mrkdwn`
blocks. LLM narrative commonly writes "~$2M" to mean "approximately $2M" —
Slack's `mrkdwn` parses a `~..~` span as strikethrough, so two such tildes
in the same message silently struck out everything between them. Swap the
literal tilde for the actual approximation sign, which means the same
thing and isn't `mrkdwn` syntax.
"""


def sanitize_mrkdwn(text: str) -> str:
    return text.replace("~", "≈")
