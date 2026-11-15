# auth

Sign in with Slack, shared by the web find-match app (`matching_engine`) and the
Wusool MCP (`mcp`).

- `authorize_url` / `identity_from_code`: the OpenID Connect exchange against the
  Toolkit's own Slack app. Each caller passes its own `redirect_uri`, and each
  redirect URL must be listed in the Slack app's OAuth settings.
- `workspace_team_id`: the workspace the bot is installed in, the only one let in.
- `is_active_member`: `False` once Slack says the person left or was deactivated,
  or is a guest when `allow_guests=False`; `None` when Slack can't be asked, so an
  outage doesn't sign everyone out.

This module holds no sessions or tokens. Each caller signs its own: the web app
its session cookie, the MCP its OAuth tokens.

Settings (`config.py`): `SLACK_BOT_TOKEN`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`.
The bot needs `users:read` for the member check.
