"""`vertical_kb` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

AMBIGUOUS / CONDITIONAL: `embedding` (`vector(1536)`) is only added by the
same guarded `DO $$ ... IF EXISTS (SELECT 1 FROM pg_extension WHERE extname =
'vector') ... END $$` block as `buyer_intel.brief_embedding`
(`004_machine_layer.sql` ~lines 137-146) — see `buyer_intel.py`'s docstring
for the full reasoning. Modeled here as the fresh-install end-state
(nullable `Vector(1536)`, present because this repo's dev `docker-compose.yml`
image ships pgvector); confirm against a live reflection before relying on
it, since a `vector`-less Postgres server never gets this column at all.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VerticalKb(Base):
    __tablename__ = "vertical_kb"
    __table_args__ = (Index("idx_vertical_kb_sector", "sector"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    sector: Mapped[str] = mapped_column(Text, nullable=False)
    tier1_research: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    source_cite: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # CONDITIONAL COLUMN — see module docstring. Only present if the `vector`
    # extension was installed when `004_machine_layer.sql` ran.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
