"""rename people to person (2026-08-30)

Table was `people`; standardizing on the singular `person` per explicit
request. Postgres does not rename dependent objects when a table itself is
renamed, so every identifier that embeds the old name is renamed alongside
it: the two column indexes, the explicitly-named owner FK, the
auto-generated company FK, and the auto-generated primary key constraint.
FKs from other tables (deals, buyer_roles, notes, graph_edges) reference
this table by OID, not name, so they need no changes.

Revision ID: 2f4edfbfb647
Revises: d5080e26bfc2
Create Date: 2026-08-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f4edfbfb647"
down_revision: str | Sequence[str] | None = "d5080e26bfc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("person"):
        return
    if not inspector.has_table("people"):
        raise RuntimeError("Neither people nor person exists")

    op.rename_table("people", "person")
    op.execute("ALTER TABLE person RENAME CONSTRAINT people_pkey TO person_pkey")
    op.execute(
        "ALTER TABLE person RENAME CONSTRAINT people_company_attio_id_fkey TO person_company_attio_id_fkey"
    )
    op.execute(
        "ALTER TABLE person RENAME CONSTRAINT people_owner_attio_id_fkey TO person_owner_attio_id_fkey"
    )
    op.execute("ALTER INDEX idx_people_company RENAME TO idx_person_company")
    op.execute("ALTER INDEX idx_people_email RENAME TO idx_person_email")
    op.execute("ALTER INDEX idx_graph_edges_people RENAME TO idx_graph_edges_person")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER INDEX idx_graph_edges_person RENAME TO idx_graph_edges_people")
    op.execute("ALTER INDEX idx_person_email RENAME TO idx_people_email")
    op.execute("ALTER INDEX idx_person_company RENAME TO idx_people_company")
    op.execute(
        "ALTER TABLE person RENAME CONSTRAINT person_owner_attio_id_fkey TO people_owner_attio_id_fkey"
    )
    op.execute(
        "ALTER TABLE person RENAME CONSTRAINT person_company_attio_id_fkey TO people_company_attio_id_fkey"
    )
    op.execute("ALTER TABLE person RENAME CONSTRAINT person_pkey TO people_pkey")
    op.rename_table("person", "people")
