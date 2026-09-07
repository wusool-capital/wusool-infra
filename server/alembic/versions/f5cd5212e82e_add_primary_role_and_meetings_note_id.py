"""add meetings.primary_role and meetings.note_id (2026-09-07)

Two changes for the meeting-note linkage correction:

1. `meetings.primary_role`, reusing the `meeting_role` enum type
   `b4e1d7c0f3a2` (this revision's parent) already created for
   `notes.primary_role` — not a new type. That migration's own rationale
   ("more than one column may come to hold it") is exactly this: the same
   seller/buyer/investor/internal/general tag, promoted here out of
   `meetings.metadata` jsonb (where `encode_role_metadata` already stashed
   it) into a queryable column on the table it originates from, so an
   internal/general meeting can be filtered out of a notes listing without
   an org to anchor it. `notes.primary_role` is set from this column at
   publish time, not derived independently.

2. `meetings.note_id`, an FK to `notes.id` — written back by the publish
   flow once a meeting's note has been created, so a meeting can be traced
   to the CRM note it produced. No downstream FK points at `meetings`, so
   this is a plain one-way edge; no `use_alter` needed.

No backfill: both databases were cleared before this change, so history
starts here. Both new columns are nullable.

Revision ID: f5cd5212e82e
Revises: b4e1d7c0f3a2
Create Date: 2026-09-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5cd5212e82e"
down_revision: str | Sequence[str] | None = "b4e1d7c0f3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "meetings",
        sa.Column(
            "primary_role",
            postgresql.ENUM(
                "seller",
                "buyer",
                "investor",
                "internal",
                "general",
                name="meeting_role",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("meetings", sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_meetings_note_id", "meetings", "notes", ["note_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_meetings_note_id", "meetings", type_="foreignkey")
    op.drop_column("meetings", "note_id")
    op.drop_column("meetings", "primary_role")
