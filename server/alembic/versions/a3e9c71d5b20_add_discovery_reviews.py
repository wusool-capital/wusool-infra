"""add discovery_reviews (2026-10-04)

Google Maps leads `discovery` held back for a human website review (AZM-134)
instead of auto-creating. Keyed by Google place id: backs the durable
"Review & Save" button and stops later runs re-posting the same lead for 30
days once its card was posted (`posted_at`). See
`app/models/discovery_review.py`. Postgres-only, never synced to Attio.

Additive, no backfill.

Revision ID: a3e9c71d5b20
Revises: 0d2458f0af59
Create Date: 2026-10-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3e9c71d5b20"
down_revision: str | Sequence[str] | None = "0d2458f0af59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "discovery_reviews",
        sa.Column("place_id", sa.Text(), primary_key=True),
        sa.Column("org_name", sa.Text(), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column(
            "flagged_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("posted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("discovery_reviews")
