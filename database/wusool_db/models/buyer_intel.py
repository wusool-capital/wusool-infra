"""`buyer_intel` — see `database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

AMBIGUOUS / CONDITIONAL: `brief_embedding` (`vector(1536)`) is only added by
a guarded `DO $$ ... IF EXISTS (SELECT 1 FROM pg_extension WHERE extname =
'vector') ... END $$` block (`004_machine_layer.sql` ~lines 137-146) — it
does not exist at all on a Postgres server without the `vector` extension
installed (plain `postgres:16-alpine`; see `001_extensions.sql`'s own
exception handler for the same condition). This repo's dev
`docker-compose.yml` uses `pgvector/pgvector:pg16`, so a *fresh install in
this repo's own dev compose stack* does get the column — that's the
fresh-install end-state modeled below (nullable `Vector(1536)`), per this
batch's instructions. Whether the live target database (dev/prod RDS) has
the `vector` extension enabled cannot be determined from the SQL files alone
— confirm via reflection before relying on this column.

`pgvector`'s SQLAlchemy integration (`pgvector.sqlalchemy.Vector`) was not
used anywhere else in this repo before this batch (`matching-engine` does no
vector search per its own README: "Not implemented (out of scope for Branch
1 by design): pgvector/embeddings"); this file introduces the pattern.
`pgvector` was added to `database/pyproject.toml`'s dependencies accordingly.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class BuyerIntel(Base):
    __tablename__ = "buyer_intel"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    buyer_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    cash_window: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    appetite_score: Mapped[Decimal | None] = mapped_column(Numeric)
    brief: Mapped[str | None] = mapped_column(Text)
    ideal_target: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # CONDITIONAL COLUMN — see module docstring. Only present if the `vector`
    # extension was installed when `004_machine_layer.sql` ran. Modeled here
    # as the fresh-install end-state for this repo's own pgvector-enabled
    # dev compose image; may not exist on every real environment.
    brief_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    buyer_organization: Mapped["Organization"] = relationship(foreign_keys=[buyer_attio_id])
