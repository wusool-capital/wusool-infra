"""add match_results.deal_attio_id (2026-09-29)

Links an approved match candidate to the Qualified deal its approval created
in Attio. Nullable with no backfill: only approvals from this change onwards
carry a deal. SET NULL so a removed deal does not delete match history.

Revision ID: c4d9a17e3b58
Revises: b2f7c48d0e91
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d9a17e3b58"
down_revision: str | None = "b2f7c48d0e91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("match_results", sa.Column("deal_attio_id", sa.Text(), nullable=True))
    op.create_foreign_key(
        "match_results_deal_attio_id_fkey",
        "match_results",
        "deals",
        ["deal_attio_id"],
        ["attio_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("match_results_deal_attio_id_fkey", "match_results", type_="foreignkey")
    op.drop_column("match_results", "deal_attio_id")
