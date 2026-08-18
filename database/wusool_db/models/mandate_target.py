"""`mandate_targets` — see `database/sql/004_machine_layer.sql`.

STATIC-ANALYSIS DRAFT derived from `database/sql/00*.sql`, not a live-DB
reflection — see `wusool_db/models/_static_analysis_notice.py` for the full
caveat before trusting this for Stage 4 (`alembic stamp head`).

`mandate.py`'s own docstring says "not mapped in this phase — no repository
or test needs it yet"; this is that model.

AMBIGUOUS (minor, naming only): the DDL declares `UNIQUE (mandate_id,
seller_attio_id)` with no explicit `CONSTRAINT` name, so Postgres assigns its
own default (`<table>_<col1>_<col2>_key`). The name used below
(`mandate_targets_mandate_id_seller_attio_id_key`) is that default-naming
convention applied by hand, not read literally from any file — confirm the
actual live constraint name via reflection; a mismatch here would make
`alembic --autogenerate` propose a harmless rename.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wusool_db.base import Base

if TYPE_CHECKING:
    from wusool_db.models.mandate import Mandate
    from wusool_db.models.organization import Organization


class MandateTarget(Base):
    __tablename__ = "mandate_targets"
    __table_args__ = (
        UniqueConstraint(
            "mandate_id",
            "seller_attio_id",
            name="mandate_targets_mandate_id_seller_attio_id_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("mandates.id", ondelete="CASCADE"), nullable=False
    )
    seller_attio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.attio_id", ondelete="CASCADE"), nullable=False
    )
    proxy_size: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    tier: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    mandate: Mapped["Mandate"] = relationship(foreign_keys=[mandate_id])
    seller_organization: Mapped["Organization"] = relationship(foreign_keys=[seller_attio_id])
