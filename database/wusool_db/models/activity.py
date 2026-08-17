"""`activities` — see `database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

`subject_attio_id`/`subject_uuid` are a polymorphic reference disambiguated
by `subject_type` (e.g. "organization" vs. some UUID-keyed table) — there is
no single table either column can be a real `ForeignKey` to, so both stay
plain columns, same as the DDL. The DB-level guarantee that at least one of
them is populated is `activities_subject_present`
(`CHECK (subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL)`),
reproduced below as a `CheckConstraint` with its original name so a future
`--autogenerate` sees no drift.

Clean otherwise: not touched again after `004_machine_layer.sql`.
"""

import uuid as uuid_
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.user import User


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL",
            name="activities_subject_present",
        ),
    )

    id: Mapped[uuid_.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Polymorphic subject reference — see module docstring. No FK: the target
    # table depends on `subject_type` and isn't fixed at the schema level.
    subject_attio_id: Mapped[str | None] = mapped_column(Text)
    subject_uuid: Mapped[uuid_.UUID | None] = mapped_column(UUID)
    actor_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.attio_id"))
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    channel: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_attio_id])
