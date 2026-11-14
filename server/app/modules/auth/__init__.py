"""Sign in with Slack, shared by the web app (`matching_engine`) and the Wusool
MCP (`mcp`): the OpenID Connect exchange and the workspace-member checks."""

from app.modules.auth.providers.slack_identity import (
    SlackIdentity,
    SlackSignInError,
    authorize_url,
    identity_from_code,
    is_active_member,
    slack_sign_in_configured,
    workspace_team_id,
)

__all__ = [
    "SlackIdentity",
    "SlackSignInError",
    "authorize_url",
    "identity_from_code",
    "is_active_member",
    "slack_sign_in_configured",
    "workspace_team_id",
]
