"""drop orphaned bot-managed columns from seller_roles

Confirmed by direct reflection against dev's real database (2026-08-18):
`seller_roles` carries three columns — removed_at, bot_managed_at
(TIMESTAMPTZ), bot_managed_by (TEXT) — that exist live but were never in
this repo's SQLAlchemy models. Traced to database/sql/008_bot_managed_
columns.sql, which was added in PR #23 and reverted shortly after ("Reverts
the previous bot-owned schema addition... schema changes are the data
engineer's call, not this bot's") — the file was removed from the repo, but
the ALTER TABLE it had already run against dev was never rolled back.

Verified safe to drop: all 210 rows in dev's seller_roles have NULL in all
three columns — nothing ever populated them, nothing currently reads them.
`IF EXISTS` throughout so this is also a safe no-op against any environment
that never had them (a fresh database, or prod if its snapshot predates
PR #23) — never fails, never assumes their presence.

Revision ID: 8d7dcb445863
Revises: eec9dde1cfbb
Create Date: 2026-08-18 01:01:23.662959

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d7dcb445863"
down_revision: str | Sequence[str] | None = "eec9dde1cfbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE seller_roles DROP COLUMN IF EXISTS removed_at;")
    op.execute("ALTER TABLE seller_roles DROP COLUMN IF EXISTS bot_managed_at;")
    op.execute("ALTER TABLE seller_roles DROP COLUMN IF EXISTS bot_managed_by;")


def downgrade() -> None:
    """Downgrade schema.

    Recreates the columns, empty — their original values (all NULL on every
    row at drop time, per this revision's own verification) are not
    recoverable from anywhere, but there is nothing to recover: nothing was
    ever stored in them.
    """
    op.add_column("seller_roles", sa.Column("bot_managed_by", sa.Text(), nullable=True))
    op.add_column(
        "seller_roles", sa.Column("bot_managed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "seller_roles", sa.Column("removed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
