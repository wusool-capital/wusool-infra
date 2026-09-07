"""add primary_role to meetings/notes and meetings.note_id (2026-09-07)

Two changes for the meeting-note linkage correction:

1. `primary_role` (seller/buyer/investor/internal/general) on both
   `meetings` and `notes` — Text + CHECK on both, deliberately not a native
   Postgres enum even on `meetings`: `meetings`' three existing enums
   (`meeting_source`, `counterparty_role`, `meeting_type`) are Scribe-owned
   (an external writer needs the type to exist independently of the table;
   see `eec9dde1cfbb`'s `scribe_pub` GRANTs), but `primary_role` is written
   only by this repo's own ingest path, so that rationale doesn't apply.
   Text is also easier for `scribe_pub` (no type dependency, no cast) and
   easier to evolve (`ALTER TYPE ADD VALUE` can't run in a transaction and a
   value can never be removed, whereas a CHECK is a plain swap). Matches
   `notes.note_type`'s own documented rationale (`app/models/note.py`) for
   avoiding a native enum on that table.

2. `meetings.note_id`, an FK to `notes.id` — written back by the publish
   flow once a meeting's note has been created, so a meeting can be traced
   to the CRM note it produced. No downstream FK points at `meetings`, so
   this is a plain one-way edge; no `use_alter` needed.

No backfill: both databases were cleared before this change, so history
starts here. All three new columns are nullable.

Revision ID: f5cd5212e82e
Revises: f7a2c9e14b83
Create Date: 2026-09-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5cd5212e82e"
down_revision: str | Sequence[str] | None = "f7a2c9e14b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRIMARY_ROLE_CHECK = "primary_role IN ('seller','buyer','investor','internal','general')"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("meetings", sa.Column("primary_role", sa.Text(), nullable=True))
    op.create_check_constraint("ck_meetings_primary_role", "meetings", _PRIMARY_ROLE_CHECK)

    op.add_column("notes", sa.Column("primary_role", sa.Text(), nullable=True))
    op.create_check_constraint("ck_notes_primary_role", "notes", _PRIMARY_ROLE_CHECK)

    op.add_column("meetings", sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_meetings_note_id", "meetings", "notes", ["note_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_meetings_note_id", "meetings", type_="foreignkey")
    op.drop_column("meetings", "note_id")

    op.drop_constraint("ck_notes_primary_role", "notes", type_="check")
    op.drop_column("notes", "primary_role")

    op.drop_constraint("ck_meetings_primary_role", "meetings", type_="check")
    op.drop_column("meetings", "primary_role")
