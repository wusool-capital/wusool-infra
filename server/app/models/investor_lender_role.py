"""`investor_lender_roles` — see `(historical, removed) database/sql/003_crm_roles.sql`.

STATIC-ANALYSIS DRAFT derived from `(historical, removed) database/sql/00*.sql`, not a live-DB
reflection — see `app/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

Same shape as `buyer_roles`/`seller_roles` (one row per organization,
`UNIQUE(org_attio_id)`, `ON DELETE CASCADE`), and no `matching-engine`/
`ddl-commands` code maps this table today, so there's no prior narrower/wider
mapping to reconcile — this is a plain read of `003_crm_roles.sql`. No
`relationship(back_populates=...)` back onto `Organization` is added here
(would require touching `organization.py`, out of scope for this batch); the
FK is expressed one-directionally instead, same as this batch's other
new-table-to-existing-table references.

Clean, no ambiguity: not touched again after `003_crm_roles.sql`.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class InvestorLenderRole(Base):
    __tablename__ = "investor_lender_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    investor_type: Mapped[str | None] = mapped_column(Text)
    stage_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    sector_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    interests: Mapped[str | None] = mapped_column(Text)
    facility_type: Mapped[str | None] = mapped_column(Text)
    activity_level: Mapped[str | None] = mapped_column(Text)
    raw_attio: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped["Organization"] = relationship(foreign_keys=[org_attio_id])
