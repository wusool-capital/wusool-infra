"""`attio_sent_values` — last value the interactions engine sent to Attio (AZM-159).

One row per record and field. A write is skipped when the new value equals
this one, so a lagging Postgres mirror never causes a resend. No FK because the
record can be an organization, a person or a deal.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttioSentValue(Base):
    __tablename__ = "attio_sent_values"
    __table_args__ = (
        CheckConstraint(
            "object IN ('organizations','person','deal')", name="attio_sent_values_object_check"
        ),
        UniqueConstraint(
            "object", "record_attio_id", "field", name="uq_attio_sent_values_record_field"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    object: Mapped[str] = mapped_column(Text, nullable=False)
    record_attio_id: Mapped[str] = mapped_column(Text, nullable=False)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    # The value as sent; NULL means the engine cleared the field.
    value: Mapped[str | None] = mapped_column(Text)
    # The seed's baseline for this field, kept beside the last value sent.
    baseline: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
