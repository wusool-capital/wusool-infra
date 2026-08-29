"""drop deals.next_task (2026-08-29)

Confirmed dead by querying DEV Attio's live `deals` object directly (the
actual source `sync-postgres.ps1`/`upsert.py` read from, not the separate
SOURCE-workspace `deal` custom object): no `next_task` or `next_due_task`
attribute exists there, active or archived (43 attributes checked). Every
sync has therefore always written NULL into this column via
`ref(v,"next_due_task") or first(v,"next_task")` in both `sync-postgres.ps1`
and `ddl_commands/modules/attio_sync/upsert.py` -- both updated in this same
change to drop the dead references alongside the column. Not present in the
target Deal schema design either.

Revision ID: d5080e26bfc2
Revises: e0c1e7522181
Create Date: 2026-08-29 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5080e26bfc2"
down_revision: str | Sequence[str] | None = "e0c1e7522181"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("deals", "next_task")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("deals", sa.Column("next_task", sa.Text(), nullable=True))
