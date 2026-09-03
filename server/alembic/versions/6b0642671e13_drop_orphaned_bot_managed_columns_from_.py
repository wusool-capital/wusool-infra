"""drop orphaned bot-managed columns from buyer_roles

Same incident as the previous revision (8d7dcb445863), one table over: PR #23
was titled "add /edit-seller, /remove-seller, /edit-buyer, /remove-buyer" —
it added these same three columns to BOTH role tables, and only
seller_roles was checked when that revision was written. Confirmed by
direct reflection against dev's real database (2026-08-18): buyer_roles
carries the identical removed_at/bot_managed_at/bot_managed_by columns,
and all 279 rows have NULL in all three — same dead, never-populated
leftover from the same reverted feature.

Revision ID: 6b0642671e13
Revises: 8d7dcb445863
Create Date: 2026-08-18 01:08:06.409543

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b0642671e13"
down_revision: str | Sequence[str] | None = "8d7dcb445863"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE buyer_roles DROP COLUMN IF EXISTS removed_at;")
    op.execute("ALTER TABLE buyer_roles DROP COLUMN IF EXISTS bot_managed_at;")
    op.execute("ALTER TABLE buyer_roles DROP COLUMN IF EXISTS bot_managed_by;")


def downgrade() -> None:
    """Downgrade schema.

    Recreates the columns, empty — same as 8d7dcb445863, there is nothing
    to recover: all rows had NULL in all three at drop time.
    """
    op.add_column("buyer_roles", sa.Column("bot_managed_by", sa.Text(), nullable=True))
    op.add_column(
        "buyer_roles", sa.Column("bot_managed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "buyer_roles", sa.Column("removed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
