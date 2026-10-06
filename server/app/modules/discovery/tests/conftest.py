"""Test fixtures. No real Slack/Google Places credentials are required to
run this suite by default — dummy env vars are set at import time.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:15432/x")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
