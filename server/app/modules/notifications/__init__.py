"""Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here, never reach into `.providers`/`.application`
directly.
"""

from app.modules.notifications.application.ports.slack import SlackNotifierPort
from app.modules.notifications.providers.slack.client import get_slack_client
from app.modules.notifications.providers.slack.notifier import SlackWebClientNotifier

__all__ = ["SlackNotifierPort", "SlackWebClientNotifier", "get_slack_client"]
