"""`notes` — unified notes table, per the "Notes" section of the Wusool
Schema Handover artifact, which this model mirrors field-for-field. Backfill
source as of 2026-08-28: SOURCE Attio's own `note` custom object
(`workflows/crm-sync/scripts/source-attio/backfill-notes.ps1`), read directly
into Postgres via `database/sync-notes-from-source.ps1` -- not through DEV
Attio, which has no notes object yet.

Replaces the separate notes fields scattered across Organization, Person,
and Buyer Role. Mastered in PostgreSQL, not Attio: backfilled from SOURCE
Attio once, written by the meeting-summary pipeline afterward, then intended
to be pushed one-way to DEV Attio purely so the team has somewhere to see it
there too (DEV side still deferred).

`organization_id` is set whenever the note has one (directly for org-level
notes, or derived via the person's/role's parent org otherwise), but is
nullable (2026-08-29): a note whose only anchor is a person or role with no
associated organization at all still needs a home. `person_id`/
`buyer_role_id`/`seller_role_id` are nullable and set only when the note is
about that more specific thing rather than the organization generally.
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
    organization_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("organizations.attio_id"), nullable=True
    )
    person_id: Mapped[str | None] = mapped_column(Text, ForeignKey("person.attio_id"))
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

    organization: Mapped["Organization | None"] = relationship(foreign_keys=[organization_id])
    person: Mapped["Person | None"] = relationship(foreign_keys=[person_id])
    buyer_role: Mapped["BuyerRole | None"] = relationship(foreign_keys=[buyer_role_id])
    seller_role: Mapped["SellerRole | None"] = relationship(foreign_keys=[seller_role_id])
