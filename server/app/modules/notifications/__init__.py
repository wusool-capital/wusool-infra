"""Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here, never reach into `.providers`/`.application`
directly.
"""

from app.modules.notifications.application.ports.slack import SlackNotifierPort
from app.modules.notifications.domain.slack_payloads import (
    SlackCommandPayload,
    SlackInteractionBody,
    SlackViewSubmissionPayload,
)
from app.modules.notifications.domain.text import sanitize_mrkdwn
from app.modules.notifications.providers.slack.bolt_app import build_bolt_app
from app.modules.notifications.providers.slack.client import get_slack_client
from app.modules.notifications.providers.slack.modals import (
    build_loading_modal,
    build_notice_modal,
    open_loading_modal,
)
from app.modules.notifications.providers.slack.notifier import SlackWebClientNotifier

__all__ = [
    "SlackCommandPayload",
    "SlackInteractionBody",
    "SlackNotifierPort",
    "SlackViewSubmissionPayload",
    "SlackWebClientNotifier",
    "build_bolt_app",
    "build_loading_modal",
    "build_notice_modal",
    "get_slack_client",
    "open_loading_modal",
    "sanitize_mrkdwn",
]
