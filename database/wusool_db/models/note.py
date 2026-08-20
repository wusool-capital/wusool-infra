"""`notes` — PROPOSED, not yet built. No DEV Attio `notes` object and no
Postgres `notes` table exist yet; this model has no Alembic migration behind
it on purpose (deferred until the feature is actually approved/built — see
the "Notes" section of the Wusool Schema Handover artifact, which this model
mirrors field-for-field).

Replaces the separate notes fields scattered today across DEV Attio's own
Organization `notes`, Person `notes`, and Buyer Role `notes`/
`additional_notes` (none of which this repo's models mirror as a `notes`
column today — Organization's SOURCE `companies.notes` is currently a
dropped column, per the artifact), plus new meeting-summary notes going
forward. Mastered in PostgreSQL, not Attio: backfilled from Attio once,
written by the meeting-summary pipeline afterward, then pushed one-way to
Attio purely so the team has somewhere to see it there too.

`organization_id` is always set (directly for org-level notes, or derived via
the person's/role's parent org otherwise); `person_id`/`buyer_role_id`/
`seller_role_id` are nullable and set only when the note is about that more
specific thing rather than the organization generally.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.buyer_role import BuyerRole
    from wusool_db.models.organization import Organization
    from wusool_db.models.person import Person
    from wusool_db.models.seller_role import SellerRole


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint("note_type IN ('Manual', 'Meeting')", name="notes_note_type_check"),
        Index("idx_notes_organization", "organization_id"),
        Index("idx_notes_person", "person_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id"), nullable=False
    )
    person_id: Mapped[str | None] = mapped_column(Text, ForeignKey("people.attio_id"))
    buyer_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("buyer_roles.id"))
    seller_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("seller_roles.id"))
    # Manual = historical/hand-entered. Meeting = generated from a meeting
    # transcript summary. Plain Text + CheckConstraint, not a native Postgres
    # enum -- no external service (unlike `meetings`' Scribe-owned enums)
    # needs this type to exist independently of this table.
    note_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization"] = relationship(foreign_keys=[organization_id])
    person: Mapped["Person | None"] = relationship(foreign_keys=[person_id])
    buyer_role: Mapped["BuyerRole | None"] = relationship(foreign_keys=[buyer_role_id])
    seller_role: Mapped["SellerRole | None"] = relationship(foreign_keys=[seller_role_id])
