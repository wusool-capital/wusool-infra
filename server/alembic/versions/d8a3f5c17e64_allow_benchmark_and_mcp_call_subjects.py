"""allow benchmark and MCP call subjects on activities (2026-11-15)

The MCP benchmark tools record each edit as an activity whose subject is the
peer cut or rule row that changed. The MCP runner records every tool call as an
activity whose subject is the call itself.

Revision ID: d8a3f5c17e64
Revises: c2f9a6e1b583
Create Date: 2026-11-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8a3f5c17e64"
down_revision: str | Sequence[str] | None = "c2f9a6e1b583"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = "'Organization','Person','Deal','BuyerRole','SellerRole','Note','Meeting'"
_AFTER = _BEFORE + ",'BenchmarkPeerCut','BenchmarkRule','McpCall'"


def _replace(values: str) -> None:
    op.drop_constraint("activities_subject_type_check", "activities", type_="check")
    # NOT VALID, as when it was created: older rows predate the closed list.
    op.execute(
        "ALTER TABLE activities ADD CONSTRAINT activities_subject_type_check "
        f"CHECK (subject_type IN ({values})) NOT VALID"
    )


def upgrade() -> None:
    """Upgrade schema."""
    _replace(_AFTER)


def downgrade() -> None:
    """Downgrade schema."""
    _replace(_BEFORE)
