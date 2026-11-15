"""Sign-in checks shared across modules: Sign in with Slack (the web app in
`matching_engine` and the Wusool MCP in `mcp`) and the Cloudflare Access token
check for the Engine."""

from app.modules.auth.providers.cloudflare_access import (
    AccessClaims,
    AccessKeysUnavailableError,
    AccessSignInError,
    access_configured,
    verify_access_jwt,
)
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
    "AccessClaims",
    "AccessKeysUnavailableError",
    "AccessSignInError",
    "SlackIdentity",
    "SlackSignInError",
    "access_configured",
    "authorize_url",
    "identity_from_code",
    "is_active_member",
    "slack_sign_in_configured",
    "verify_access_jwt",
    "workspace_team_id",
]
