"""Test fixtures.

No real database connection or secrets are required to run this suite. Dummy
env vars are set at import time (before any test module imports `app.main`,
which reads settings at module load) so collection never needs a real .env.
The async engine is constructed but never connected unless a test explicitly
hits `/readiness`.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("LLM_MODEL_EXTRACTION", "claude-haiku-4-5-20251001")
os.environ.setdefault("LLM_MODEL_REASONING", "claude-sonnet-5")
