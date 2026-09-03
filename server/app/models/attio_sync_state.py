"""`attio_sync_state` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

`metadata` collides with `DeclarativeBase.metadata`, so the mapped attribute
is `metadata_` with an explicit column-name override — same pattern already
used for `meetings.metadata` (`meeting.py`) and `match_results.metadata`
(`match_result.py`).

Note (not an ambiguity, just easy to miss): this table has no `created_at`
column at all, only `updated_at` — that matches the DDL exactly, not an
omission here.

Clean otherwise: not touched again after `004_machine_layer.sql`.
"""

from datetime import datetime

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttioSyncState(Base):
    __tablename__ = "attio_sync_state"

    sync_name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_cursor: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
