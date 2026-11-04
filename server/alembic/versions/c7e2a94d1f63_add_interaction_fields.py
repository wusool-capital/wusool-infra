"""add interaction fields to organizations and person (2026-11-05)

AZM-159: Attio computes last interaction / connection strength only on its
standard Companies and People objects, so Organizations and Person carry a
stale one-time copy. The interactions engine will compute these fields and
write them to Attio; the webhook mirror (`ddl_commands/persistence/attio_sync.py`)
copies them here. `last_interaction_at` and `connection_strength` already exist.

All columns nullable, no backfill: the mirror fills them as Attio values land.
The two actor columns reference `users.attio_id` like `owner_attio_id`; the
mirror stores NULL for an unknown workspace member. Grants are re-applied by
`utilities/db_roles.py` after `alembic upgrade head`.

Rollback: `alembic downgrade -1` drops the foreign keys, then the 22 columns.
No other object depends on them.

Revision ID: c7e2a94d1f63
Revises: b2d9f6a3c418
Create Date: 2026-11-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2a94d1f63"
down_revision: str | Sequence[str] | None = "b2d9f6a3c418"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("organizations", "person")
_TIMESTAMP_COLUMNS = (
    "first_interaction_at",
    "next_interaction_at",
    "first_email_interaction_at",
    "last_email_interaction_at",
    "first_calendar_interaction_at",
    "last_calendar_interaction_at",
    "next_calendar_interaction_at",
)
_TEXT_COLUMNS = ("last_interaction_channel", "last_interaction_subject")
_ACTOR_COLUMNS = ("last_interaction_owner", "strongest_connection_user")


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        for column in _TIMESTAMP_COLUMNS:
            op.add_column(
                table, sa.Column(column, postgresql.TIMESTAMP(timezone=True), nullable=True)
            )
        for column in (*_TEXT_COLUMNS, *_ACTOR_COLUMNS):
            op.add_column(table, sa.Column(column, sa.Text(), nullable=True))
        for column in _ACTOR_COLUMNS:
            op.create_foreign_key(f"{table}_{column}_fkey", table, "users", [column], ["attio_id"])


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        for column in _ACTOR_COLUMNS:
            op.drop_constraint(f"{table}_{column}_fkey", table, type_="foreignkey")
        for column in (*_TIMESTAMP_COLUMNS, *_TEXT_COLUMNS, *_ACTOR_COLUMNS):
            op.drop_column(table, column)
