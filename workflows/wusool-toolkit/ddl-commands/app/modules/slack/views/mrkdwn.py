"""Sanitization for free-form text embedded in Slack `mrkdwn` blocks. A
literal `~` is parsed by Slack as strikethrough syntax — swap it for the
actual approximation sign, which means the same thing and isn't `mrkdwn`
syntax. Mirrors matching-engine's `views/mrkdwn.py`.
"""


def sanitize_mrkdwn(text: str) -> str:
    return text.replace("~", "≈")
