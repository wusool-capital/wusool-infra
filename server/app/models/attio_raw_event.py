"""`attio_raw_events` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Note (not an ambiguity, just easy to miss): `payload` is `NOT NULL` with
**no** `server_default` — unlike every other `jsonb` column in this batch,
callers must always supply a value. That's a literal read of the DDL
(`payload jsonb NOT NULL` — no `DEFAULT` clause), not an omission here.
`idempotency_key` is `UNIQUE` but nullable (no `NOT NULL` in the DDL).

Clean otherwise: not touched again after `004_machine_layer.sql`.
"""

import uuid
from datetime import datetime

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttioRawEvent(Base):
    __tablename__ = "attio_raw_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
