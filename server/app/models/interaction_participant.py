"""`interaction_participants` — one address on an interaction (AZM-159).

Person and Organization links are filled once the record exists, so
earlier interactions attach to a contact created later. Postgres-only.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InteractionParticipant(Base):
    __tablename__ = "interaction_participants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('from','to','cc','attendee')", name="interaction_participants_role_check"
        ),
        UniqueConstraint(
            "interaction_id", "email", "role", name="uq_interaction_participants_address"
        ),
        Index("idx_interaction_participants_email", "email"),
        Index("idx_interaction_participants_domain", "domain"),
        Index("idx_interaction_participants_person", "person_attio_id"),
        Index("idx_interaction_participants_organization", "organization_attio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False
    )
    # Lowercased; team aliases are normalised to one address before insert.
    email: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Nulled, not cascaded: the interaction history outlives a deleted record.
    person_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("person.attio_id", ondelete="SET NULL")
    )
    organization_attio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
