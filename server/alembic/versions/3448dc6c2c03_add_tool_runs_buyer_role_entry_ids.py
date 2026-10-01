"""add tool_runs.buyer_role_entry_ids (2026-09-30)

A Buyer Network submission now creates one buyer_role per ticked vertical, and
`buyer_role_id` can hold only one. Attio entry ids, not buyer_roles.id: the
mirror lands those rows after the run finishes. No backfill: every earlier run
made exactly one role, which `buyer_role_id` already covers.

Revision ID: 3448dc6c2c03
Revises: c4d9a17e3b58
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "3448dc6c2c03"
down_revision: str | None = "c4d9a17e3b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tool_runs",
        sa.Column(
            "buyer_role_entry_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("tool_runs", "buyer_role_entry_ids")
