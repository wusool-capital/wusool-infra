"""add desktop push status columns to meetings

Additive-only: adds the columns and constraints the new `meetings` module
(landing in a later phase, see app.models.meeting's module docstring) needs
to track desktop-push summarization state, without touching Scribe's
existing columns.

Revision ID: 2565f7950641
Revises: 2f4edfbfb647
Create Date: 2026-09-05 13:07:13.855665

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2565f7950641'
down_revision: str | Sequence[str] | None = '2f4edfbfb647'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "meetings",
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
    )
    op.add_column("meetings", sa.Column("install_id", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("local_recording_id", sa.Text(), nullable=True))
    op.add_column(
        "meetings",
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("summary_started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_meetings_status",
        "meetings",
        "status IN ('summarizing','completed','failed')",
    )
    op.create_index(
        "uq_meetings_desktop_push",
        "meetings",
        ["install_id", "local_recording_id"],
        unique=True,
        postgresql_where=sa.text("install_id IS NOT NULL"),
    )
    op.create_index(
        "ix_meetings_summarizing",
        "meetings",
        ["summary_started_at"],
        postgresql_where=sa.text("status = 'summarizing'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_meetings_summarizing", table_name="meetings")
    op.drop_index("uq_meetings_desktop_push", table_name="meetings")
    op.drop_constraint("ck_meetings_status", "meetings", type_="check")
    op.drop_column("meetings", "summary_started_at")
    op.drop_column("meetings", "summary_json")
    op.drop_column("meetings", "local_recording_id")
    op.drop_column("meetings", "install_id")
    op.drop_column("meetings", "status")
