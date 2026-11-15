"""`auto_create_keys` — records the interactions engine created in Attio (AZM-159).

Written right after the Attio create, so a retry finds the key and never
creates the same Person or Organization twice.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AutoCreateKey(Base):
    __tablename__ = "auto_create_keys"
    __table_args__ = (
        CheckConstraint("kind IN ('person','organization')", name="auto_create_keys_kind_check"),
        UniqueConstraint("kind", "key", name="uq_auto_create_keys_kind_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # Lower-cased email for a person, domain for an organization.
    key: Mapped[str] = mapped_column(Text, nullable=False)
    record_attio_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
