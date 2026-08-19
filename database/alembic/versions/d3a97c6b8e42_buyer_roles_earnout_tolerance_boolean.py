"""change buyer_roles.earnout_tolerance to boolean (2026-08-19)

Was declared `text` (003_crm_roles.sql), but the real DEV Attio attribute is
type "checkbox" — a genuine boolean, not free text. Both sync-postgres.ps1
and the real-time webhook sync (upsert.py) were already calling their
boolean() helper on it and relying on lenient driver behavior to get away
with binding a Python bool to a text column; this migration fixes the
column itself to match reality instead of continuing to work around the
mismatch.

Checked live DEV data before writing this: all 276 buyer_role entries with
a populated value have the same value (False) -- a plain `::boolean` cast
is safe, nothing ambiguous to convert. Confirmed via the Attio API,
2026-08-19.

Revision ID: d3a97c6b8e42
Revises: c4f8e29a5d17
Create Date: 2026-08-19 10:35:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3a97c6b8e42"
down_revision: str | Sequence[str] | None = "c4f8e29a5d17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE buyer_roles ALTER COLUMN earnout_tolerance TYPE boolean "
        "USING earnout_tolerance::boolean"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE buyer_roles ALTER COLUMN earnout_tolerance TYPE text "
        "USING earnout_tolerance::text"
    )
