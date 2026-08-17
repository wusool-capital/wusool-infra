"""`organizations` — the parent entity. Buyer/seller roles are memberships on
it, never independent records (see `database/sql/002_core_attio_mirror.sql`,
`003_crm_roles.sql`).

Only the columns this bot actually reads/displays/edits are mapped here —
the real table has more (type, domains, categories, owner_attio_id,
raw_attio, ...) that this bot never touches. SQLAlchemy doesn't require
mapping every column; the real DB constraints are enforced by Postgres
regardless of what the ORM declares. `description`/`client_type`/
`estimated_arr`/`funding_raised` were added when `/edit-seller`/`/edit-buyer`
became able to edit organization-level fields too — these columns already
existed in the real schema (`002_core_attio_mirror.sql`), this only maps
them in the ORM, it is not a schema change.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ddl_commands.shared.database.base import Base

if TYPE_CHECKING:
    from ddl_commands.modules.buyers.infrastructure.models import BuyerRole
    from ddl_commands.modules.sellers.infrastructure.models import SellerRole


class Organization(Base):
    __tablename__ = "organizations"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    hq_country: Mapped[str | None] = mapped_column(Text)
    geographic_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    sector_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    client_type: Mapped[str | None] = mapped_column(Text)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    estimated_arr: Mapped[str | None] = mapped_column(Text)
    # Money shape confirmed from database/sync-postgres.ps1: {"amount": ..., "currency": ...}
    # or the column is NULL entirely — never fabricated when absent.
    funding_raised: Mapped[dict | None] = mapped_column(JSONB)
    # Attio-owned (database/sql/002_core_attio_mirror.sql, set/cleared by
    # database/sync-postgres.ps1) — read-only here, checked before any Attio
    # write so this bot never PATCHes a record Attio no longer has.
    removed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    buyer_role: Mapped["BuyerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    seller_role: Mapped["SellerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
