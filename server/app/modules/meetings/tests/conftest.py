"""Test fixtures.

Dummy env vars are set at import time (before any test module calls
`app.modules.meetings.config.get_settings()`, which requires
`DESKTOP_API_KEY` with no default) so collection never needs a real
.env, matching `ddl_commands/tests/conftest.py`.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("DESKTOP_API_KEY", "test-desktop-api-key")
