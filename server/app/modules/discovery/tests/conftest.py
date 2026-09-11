"""Test fixtures. No real Slack/Firecrawl credentials are required to run
this suite by default — dummy env vars are set at import time.
"""

import os

os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
