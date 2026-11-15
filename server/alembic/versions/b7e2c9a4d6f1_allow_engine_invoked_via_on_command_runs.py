"""allow command_runs.invoked_via = 'engine' (2026-11-15, AZM-180)

The Engine frontend writes buyers and sellers through the Toolkit API, so the
ledger must accept runs invoked from it. `activities.source` has no CHECK, so
it needs no change.

Revision ID: b7e2c9a4d6f1
Revises: d8a3f5c17e64
Create Date: 2026-11-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c9a4d6f1"
down_revision: str | Sequence[str] | None = "d8a3f5c17e64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("command_runs_invoked_via_check", "command_runs", type_="check")
    op.create_check_constraint(
        "command_runs_invoked_via_check",
        "command_runs",
        "invoked_via IN ('slack','discovery','mcp','engine')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if any 'engine' rows exist; delete them first to roll back.
    op.drop_constraint("command_runs_invoked_via_check", "command_runs", type_="check")
    op.create_check_constraint(
        "command_runs_invoked_via_check",
        "command_runs",
        "invoked_via IN ('slack','discovery','mcp')",
    )
