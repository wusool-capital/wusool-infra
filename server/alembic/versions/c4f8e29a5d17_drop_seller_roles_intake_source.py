"""drop seller_roles.intake_source (2026-08-19)

Redundant with Organization.lead_source now that lead_source exists and is
populated on every migrated organization. Checked live DEV data before
writing this: 171 of 214 seller_role entries have intake_source populated,
but every single one is the same value ("Direct") — a constant, not a real
signal — so dropping it loses no distinguishing information. Confirmed by
direct read of the DEV Attio API, 2026-08-19. The DEV Attio attribute itself
is archived (not deleted, per Attio's own option-permanence model), not
touched by this migration.

Revision ID: c4f8e29a5d17
Revises: b91d4a7f0526
Create Date: 2026-08-19 09:58:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8e29a5d17"
down_revision: str | Sequence[str] | None = "b91d4a7f0526"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("idx_seller_roles_intake_source", table_name="seller_roles")
    op.drop_column("seller_roles", "intake_source")


def downgrade() -> None:
    """Downgrade schema.

    Recreates the column, empty — its only ever-recorded value ("Direct",
    per this revision's own verification) is not worth guessing back in.
    """
    op.add_column("seller_roles", sa.Column("intake_source", sa.Text(), nullable=True))
    op.create_index(
        "idx_seller_roles_intake_source", "seller_roles", ["intake_source"]
    )
