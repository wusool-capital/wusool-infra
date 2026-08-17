"""`deal_stage_events` — see `database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

`deal.py`'s own docstring says "not mapped in this phase — add it later
against the same pattern once something reads it"; this is that model,
following the same pattern (`deals.attio_id` text PK, plain FK reference,
no `back_populates` back onto `Deal` since that would require touching
`deal.py`, out of scope here).

Clean, no ambiguity: not touched again after `004_machine_layer.sql`.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.deal import Deal


class DealStageEvent(Base):
    __tablename__ = "deal_stage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    deal_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("deals.attio_id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[str | None] = mapped_column(Text)
    to_stage: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    deal: Mapped["Deal"] = relationship(foreign_keys=[deal_attio_id])
