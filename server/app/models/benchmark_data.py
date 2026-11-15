"""The GCC SME Benchmark's peer dataset, in two tables. Owned by the
`benchmark_data` module.

`benchmark_peer_cuts` holds one row per sector (`sme`) or funding stage
(`tech`) with its percentile anchors. `benchmark_rules` holds the revenue bands
and the metric weights. Both keep only the current values: `updated_by` (the
editor's name) and `updated_at` say who last changed a row; the Slack id is on the
row's `activities` event. Version history
belongs to the audit tables.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_MODE_CHECK = "mode IN ('sme','tech')"


class BenchmarkPeerCut(Base):
    __tablename__ = "benchmark_peer_cuts"
    __table_args__ = (
        CheckConstraint(_MODE_CHECK, name="benchmark_peer_cuts_mode_check"),
        UniqueConstraint("mode", "key", name="uq_benchmark_peer_cuts_mode_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    multi_site: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    b2b: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # {metric key: [p10, p25, p50, p75, p90]}. Validated by `AnchorSet` on every read and write.
    anchors: Mapped[dict[str, list[float]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class BenchmarkRule(Base):
    """A revenue band (`kind = 'band'`) or a metric weight (`kind = 'metric'`).

    Each kind fills its own columns and leaves the other's empty.
    """

    __tablename__ = "benchmark_rules"
    __table_args__ = (
        CheckConstraint("kind IN ('band','metric')", name="benchmark_rules_kind_check"),
        CheckConstraint("mode IS NULL OR " + _MODE_CHECK, name="benchmark_rules_mode_check"),
        CheckConstraint("weight IS NULL OR weight >= 0", name="benchmark_rules_weight_check"),
        CheckConstraint(
            "(kind = 'band' AND mode IS NULL AND ebitda_adj IS NOT NULL"
            " AND rev_emp_mult IS NOT NULL AND rent_mult IS NOT NULL AND unit IS NULL"
            " AND higher_is_better IS NULL AND weight IS NULL AND observed IS NULL)"
            " OR (kind = 'metric' AND mode IS NOT NULL AND unit IS NOT NULL"
            " AND higher_is_better IS NOT NULL AND weight IS NOT NULL AND max_usd IS NULL"
            " AND ebitda_adj IS NULL AND rev_emp_mult IS NULL AND rent_mult IS NULL)",
            name="benchmark_rules_kind_columns_check",
        ),
        Index(
            "uq_benchmark_rules_band", "code", unique=True, postgresql_where=text("kind = 'band'")
        ),
        Index(
            "uq_benchmark_rules_metric",
            "mode",
            "code",
            unique=True,
            postgresql_where=text("kind = 'metric'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # Band columns. `max_usd` is NULL on the open-ended top band.
    max_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    ebitda_adj: Mapped[Decimal | None] = mapped_column(Numeric)
    rev_emp_mult: Mapped[Decimal | None] = mapped_column(Numeric)
    rent_mult: Mapped[Decimal | None] = mapped_column(Numeric)
    # Metric columns. `observed` is set on tech metrics only.
    unit: Mapped[str | None] = mapped_column(Text)
    higher_is_better: Mapped[bool | None] = mapped_column(Boolean)
    weight: Mapped[int | None] = mapped_column(Integer)
    observed: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
