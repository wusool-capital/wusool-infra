"""`graph_edges` — see `database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Two FKs to the same table (`people`), so both relationships need an explicit
`foreign_keys=` to disambiguate. The DDL's `graph_edges_not_self` CHECK
(`person_a_attio_id <> person_b_attio_id`) is reproduced below with its
original name so a future `--autogenerate` sees no drift.

Clean otherwise: not touched again after `004_machine_layer.sql`.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.person import Person


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        CheckConstraint(
            "person_a_attio_id <> person_b_attio_id", name="graph_edges_not_self"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    person_a_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("people.attio_id", ondelete="CASCADE"), nullable=False
    )
    person_b_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("people.attio_id", ondelete="CASCADE"), nullable=False
    )
    hop: Mapped[str] = mapped_column(Text, nullable=False)
    basis: Mapped[str | None] = mapped_column(Text)
    source_cite: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    person_a: Mapped["Person"] = relationship(foreign_keys=[person_a_attio_id])
    person_b: Mapped["Person"] = relationship(foreign_keys=[person_b_attio_id])
