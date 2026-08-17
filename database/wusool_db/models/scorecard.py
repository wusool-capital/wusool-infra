"""`scorecards` — see `database/sql/004_machine_layer.sql` (~line 193, after
the `seller_roles.relationship_status` `ALTER TABLE` — a late addition in
that file, not part of its initial batch of `CREATE TABLE`s, but with no
further changes after its own creation).

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Clean, no ambiguity.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.user import User


class Scorecard(Base):
    __tablename__ = "scorecards"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    week_start: Mapped[date | None] = mapped_column()
    created_by_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.attio_id")
    )
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_attio_id])
