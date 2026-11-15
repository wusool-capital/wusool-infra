"""The GCC SME Benchmark peer dataset: revenue bands, metric weights, peer cuts
(sectors in `sme` mode, funding stages in `tech` mode) and their percentile
anchors. Owned by the `benchmark_data` module.

`benchmark_dataset_version` is a single row bumped by every edit, so a
benchmark result can be tied to the dataset it was scored against.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_MODE_CHECK = "mode IN ('sme','tech')"


class BenchmarkBand(Base):
    __tablename__ = "benchmark_bands"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL is the open-ended top band.
    max_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    ebitda_adj: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    rev_emp_mult: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    rent_mult: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BenchmarkMetric(Base):
    __tablename__ = "benchmark_metrics"
    __table_args__ = (
        CheckConstraint(_MODE_CHECK, name="benchmark_metrics_mode_check"),
        CheckConstraint("weight >= 0", name="benchmark_metrics_weight_check"),
    )

    mode: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    # Tech metrics only: observed in the sample rather than modelled.
    observed: Mapped[bool | None] = mapped_column(Boolean)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BenchmarkPeerCut(Base):
    __tablename__ = "benchmark_peer_cuts"
    __table_args__ = (CheckConstraint(_MODE_CHECK, name="benchmark_peer_cuts_mode_check"),)

    mode: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    multi_site: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    b2b: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BenchmarkAnchor(Base):
    __tablename__ = "benchmark_anchors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mode", "peer_key"],
            ["benchmark_peer_cuts.mode", "benchmark_peer_cuts.key"],
            ondelete="CASCADE",
            name="benchmark_anchors_peer_cut_fkey",
        ),
        CheckConstraint(
            "p10 <= p25 AND p25 <= p50 AND p50 <= p75 AND p75 <= p90",
            name="benchmark_anchors_ordered_check",
        ),
    )

    mode: Mapped[str] = mapped_column(Text, primary_key=True)
    peer_key: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    p10: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    p25: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    p50: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    p75: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    p90: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BenchmarkDatasetVersion(Base):
    __tablename__ = "benchmark_dataset_version"
    __table_args__ = (CheckConstraint("id = 1", name="benchmark_dataset_version_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default="1")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
