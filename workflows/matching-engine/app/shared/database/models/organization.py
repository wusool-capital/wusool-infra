"""`organizations` — the parent entity. Buyer/seller roles are memberships on it,
never independent records (see `scripts/db/sql/002_core_attio_mirror.sql`,
`003_crm_roles.sql`).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base

if TYPE_CHECKING:
    from app.modules.buyers.infrastructure.models import BuyerRole
    from app.modules.sellers.infrastructure.models import SellerRole
    from app.shared.database.models.deal import Deal
    from app.shared.database.models.mandate import Mandate
    from app.shared.database.models.person import Person


class Organization(Base):
    __tablename__ = "organizations"

    attio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    client_type: Mapped[str | None] = mapped_column(Text)
    sector_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    stage_focus: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    geographic_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    hq_country: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    relationship_status: Mapped[str | None] = mapped_column(Text)
    connection_strength: Mapped[str | None] = mapped_column(Text)
    # Plain column, no FK object: `users` is not mapped in this phase since
    # nothing needs to traverse to it. The real DB FK constraint still exists
    # and is enforced by Postgres regardless of what the ORM declares.
    owner_attio_id: Mapped[str | None] = mapped_column(Text)
    last_interaction_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    buyer_role: Mapped["BuyerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    seller_role: Mapped["SellerRole | None"] = relationship(
        back_populates="organization", uselist=False
    )
    people: Mapped[list["Person"]] = relationship(back_populates="company")
    deals_as_buyer: Mapped[list["Deal"]] = relationship(
        foreign_keys="Deal.buyer_organization_attio_id", back_populates="buyer_organization"
    )
    deals_as_seller: Mapped[list["Deal"]] = relationship(
        foreign_keys="Deal.seller_organization_attio_id", back_populates="seller_organization"
    )
    mandates_as_buyer: Mapped[list["Mandate"]] = relationship(
        foreign_keys="Mandate.buyer_attio_id", back_populates="buyer_organization"
    )
    mandates_as_seller: Mapped[list["Mandate"]] = relationship(
        foreign_keys="Mandate.seller_attio_id", back_populates="seller_organization"
    )
