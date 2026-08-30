"""`users` — see `database/sql/002_core_attio_mirror.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Never mapped before this batch: `organizations.owner_attio_id`,
`person.owner_attio_id`, and `deals.owner_attio_id` all reference this table
but were deliberately left as plain columns (no `ForeignKey` object) when
those files were written, since `users` didn't exist as a model yet — see
each of those files' own comments. Not revisited here: retrofitting those to
real `ForeignKey`/`relationship` objects would touch Stage 1's already-landed
files, which is out of scope for this batch. New FK columns added in this
batch that reference `users.attio_id` (`activities.actor_attio_id`,
`scorecards.created_by_attio_id`) do use a real `ForeignKey` object, since
there's no such legacy constraint for them.

Clean, no ambiguity: this table's shape did not change after
`002_core_attio_mirror.sql`; no later file touches it.
"""

from datetime import datetime

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from wusool_db.base import Base


class User(Base):
    __tablename__ = "users"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    access: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
