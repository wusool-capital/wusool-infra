"""make notes.organization_id nullable (2026-08-29)

`backfill-notes.ps1` (2026-08-29) now migrates a Person's native notes with
organization_id left blank when that Person has no company at all in SOURCE
Attio, instead of skipping them outright -- some contacts (and, per the
meeting-summary pipeline, some meetings) genuinely have no associated
organization. `notes.organization_id NOT NULL` would reject exactly those
rows once `sync-notes-from-source.ps1` is built to populate this table.
person_id/buyer_role_id/seller_role_id already tolerate this (all nullable);
organization_id should too, since a note tied only to a person or a role
still has a genuine home.

Revision ID: e0c1e7522181
Revises: c3d7f2a856e1
Create Date: 2026-08-29 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0c1e7522181"
down_revision: str | Sequence[str] | None = "c3d7f2a856e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("notes", "organization_id", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("notes", "organization_id", existing_type=sa.Text(), nullable=False)
