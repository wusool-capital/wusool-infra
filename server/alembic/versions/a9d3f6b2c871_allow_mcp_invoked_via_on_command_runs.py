"""allow command_runs.invoked_via = 'mcp' (2026-11-14, AZM-171)

MCP v1 runs the buyer and seller writes outside Slack, so the ledger must
accept runs invoked over MCP. `activities.source` has no CHECK, so it needs
no change.

Revision ID: a9d3f6b2c871
Revises: e4c7a2d91f35
Create Date: 2026-11-14 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d3f6b2c871"
down_revision: str | Sequence[str] | None = "e4c7a2d91f35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("command_runs_invoked_via_check", "command_runs", type_="check")
    op.create_check_constraint(
        "command_runs_invoked_via_check",
        "command_runs",
        "invoked_via IN ('slack','discovery','mcp')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if any 'mcp' rows exist; delete them first to roll back.
    op.drop_constraint("command_runs_invoked_via_check", "command_runs", type_="check")
    op.create_check_constraint(
        "command_runs_invoked_via_check",
        "command_runs",
        "invoked_via IN ('slack','discovery')",
    )
