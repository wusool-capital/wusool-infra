"""add meetings.user_notes (2026-11-14, AZM-173)

Holds the markdown notes a user types in the desktop app during a meeting.
Nullable: meetings pushed before notes existed, and Zoom/Fireflies rows,
have none.

Revision ID: b7e1c4d8a203
Revises: a9d3f6b2c871
Create Date: 2026-11-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e1c4d8a203"
down_revision: str | Sequence[str] | None = "a9d3f6b2c871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("meetings", sa.Column("user_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("meetings", "user_notes")
