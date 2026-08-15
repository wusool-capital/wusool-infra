"""`organizations` — the parent entity. Buyer/seller roles are memberships on
it, never independent records (see `database/sql/002_core_attio_mirror.sql`,
`003_crm_roles.sql`).

Only the columns this bot actually reads/displays are mapped here (name,
hq_country, geographic_focus, sector_focus, relationship_status) — the real
table has more (description, type, domains, categories, owner_attio_id,
raw_attio, ...) that this bot never touches. SQLAlchemy doesn't require
mapping every column; the real DB constraints are enforced by Postgres
regardless of what the ORM declares.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base

if TYPE_CHECKING:
    from app.modules.buyers.infrastructure.models import BuyerRole
    from app.modules.sellers.infrastructure.models import SellerRole


class Organization(Base):
    __tablename__ = "organizations"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    hq_country: Mapped[str | None] = mapped_column(Text)
    geographic_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    sector_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    relationship_status: Mapped[str | None] = mapped_column(Text)

    buyer_role: Mapped["BuyerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    seller_role: Mapped["SellerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
