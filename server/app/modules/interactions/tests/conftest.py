"""Test fixtures. No real database or Google credentials are needed for the unit suite:
a dummy URL is set at import time so `InteractionsSettings` can be built.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:15432/x")
