"""add deals.deal_status (2026-11-14, AZM-169)

Attio Deal_V2 splits the old 20-value `deal_stage` into 10 stages plus a new
`deal_status` select (Active, On hold, Passed, Lost). This mirrors it.

Plain nullable text, like `stage`: Attio owns the option list, and a CHECK
here would make a new Attio option fail the sync instead of syncing.

Revision ID: e4c7a2d91f35
Revises: d5f8b2a17c94
Create Date: 2026-11-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4c7a2d91f35"
down_revision: str | Sequence[str] | None = "d5f8b2a17c94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("deals", sa.Column("deal_status", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deals", "deal_status")
