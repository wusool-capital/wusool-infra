"""add organizations.source_place_id and the narrowing GIN indexes (2026-09-29)

`source_place_id` is the Google Places id for an organization discovery
sourced. It is the dedupe backstop for the CRM pre-filter: a place already in
the CRM must not be re-created under a slightly different name, and a name
comparison cannot decide that reliably -- "Al Futtaim" and "Al-Futtaim Group"
are the same company, "Home" and "Home" are usually not.

The unique index is PARTIAL. The column is null on every organization that
came from SOURCE or a form, which is most of them, and a plain UNIQUE would
permit only one such row.

The two GIN indexes exist so the SQL narrowing is actually faster than the
Python loop it replaces. `sector_focus` and `geographic_focus` are
`ARRAY(Text)`, and array containment (`sector_focus @> ARRAY[...]`) cannot use
a btree -- without a GIN index the query plans as a sequential scan, which
would make the rewrite pointless.

Nullable with no backfill: nothing populates it until discovery is repointed.

Revision ID: b2f7c48d0e91
Revises: d8e4b1c60f27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2f7c48d0e91"
down_revision: str | None = "d8e4b1c60f27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("source_place_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_organizations_source_place_id",
        "organizations",
        ["source_place_id"],
        unique=True,
        postgresql_where=sa.text("source_place_id IS NOT NULL"),
    )
    op.create_index(
        "idx_organizations_sector_focus",
        "organizations",
        ["sector_focus"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_organizations_geographic_focus",
        "organizations",
        ["geographic_focus"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_organizations_geographic_focus", table_name="organizations")
    op.drop_index("idx_organizations_sector_focus", table_name="organizations")
    op.drop_index("ix_organizations_source_place_id", table_name="organizations")
    op.drop_column("organizations", "source_place_id")
