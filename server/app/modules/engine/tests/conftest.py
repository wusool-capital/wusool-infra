"""Dummy env vars so collection never needs a real `.env` or AWS."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ["AWS_SECRETS_MANAGER_SECRET_ID"] = ""
