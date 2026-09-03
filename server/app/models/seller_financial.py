"""`seller_financials` — see `(historical, removed) database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Clean, no ambiguity: not touched again after `004_machine_layer.sql`.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class SellerFinancial(Base):
    __tablename__ = "seller_financials"
    __table_args__ = (Index("idx_seller_financials_seller", "seller_attio_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    seller_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    normalised_ebitda_sde: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    add_backs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    proxy_revenue: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    source_cite: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    seller_organization: Mapped["Organization"] = relationship(foreign_keys=[seller_attio_id])
