"""add meetings.removed_at (2026-09-28)

Soft-delete marker for the desktop app's new delete flow (AZM-126): a
meeting deleted from Scribe can optionally also be removed from RDS. Mirrors
`notes.removed_at` (migration b8c41e7d09a2) rather than a hard delete, so a
mistaken delete stays recoverable and nothing has to reason about cascading
into `notes`/`matching_engine` reads.

Nullable, no backfill. `scribe_pub` already has table-level UPDATE
(eec9dde1cfbb), which covers writing this new column too.

Revision ID: 0d2458f0af59
Revises: d8e4b1c60f27
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d2458f0af59"
down_revision: str | Sequence[str] | None = "d8e4b1c60f27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "meetings", sa.Column("removed_at", postgresql.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("meetings", "removed_at")
