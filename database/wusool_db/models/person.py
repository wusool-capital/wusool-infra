"""`people` — real table name (not `persons`); see `002_core_attio_mirror.sql`."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.organization import Organization


class Person(Base):
    __tablename__ = "people"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    company_attio_id: Mapped[str | None] = mapped_column(Text, ForeignKey("organizations.attio_id"))
    email: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    linkedin: Mapped[str | None] = mapped_column(Text)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    connection_strength: Mapped[str | None] = mapped_column(Text)
    owner_attio_id: Mapped[str | None] = mapped_column(Text)
    past_employers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    education: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    enrichment: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_interaction_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped["Organization | None"] = relationship(back_populates="people")
