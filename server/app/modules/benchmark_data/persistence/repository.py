"""Postgres adapter for `BenchmarkDataRepository`. Maps rows to domain values;
ORM types never leave this file."""

from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_data import (
    BenchmarkAnchor,
    BenchmarkBand,
    BenchmarkDatasetVersion,
    BenchmarkMetric,
    BenchmarkPeerCut,
)
from app.modules.benchmark_data.domain.dataset import (
    Anchors,
    Band,
    BenchmarkDataset,
    Metric,
    Mode,
    PeerCut,
)

_MODES: tuple[Mode, ...] = ("sme", "tech")


def _mode(value: str) -> Mode:
    if value == "sme":
        return "sme"
    if value == "tech":
        return "tech"
    raise ValueError(f"Unknown benchmark mode {value!r}")


class PostgresBenchmarkDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self) -> BenchmarkDataset:
        session = self._session
        bands = (
            await session.scalars(select(BenchmarkBand).order_by(BenchmarkBand.position))
        ).all()
        metric_rows = (
            await session.scalars(
                select(BenchmarkMetric).order_by(BenchmarkMetric.mode, BenchmarkMetric.position)
            )
        ).all()
        cut_rows = (
            await session.scalars(
                select(BenchmarkPeerCut).order_by(BenchmarkPeerCut.mode, BenchmarkPeerCut.key)
            )
        ).all()
        anchor_rows = (await session.scalars(select(BenchmarkAnchor))).all()
        version = await session.get_one(BenchmarkDatasetVersion, 1)

        anchors: dict[tuple[str, str], dict[str, Anchors]] = {}
        for a in anchor_rows:
            anchors.setdefault((a.mode, a.peer_key), {})[a.metric] = (
                float(a.p10),
                float(a.p25),
                float(a.p50),
                float(a.p75),
                float(a.p90),
            )

        return BenchmarkDataset(
            version=version.version,
            updated_at=version.updated_at,
            bands=tuple(
                Band(
                    id=b.id,
                    label=b.label,
                    max_usd=None if b.max_usd is None else float(b.max_usd),
                    ebitda_adj=float(b.ebitda_adj),
                    rev_emp_mult=float(b.rev_emp_mult),
                    rent_mult=float(b.rent_mult),
                )
                for b in bands
            ),
            metrics={
                mode: {
                    m.key: Metric(
                        key=m.key,
                        label=m.label,
                        unit=m.unit,
                        higher_is_better=m.higher_is_better,
                        weight=m.weight,
                        observed=m.observed,
                    )
                    for m in metric_rows
                    if m.mode == mode
                }
                for mode in _MODES
            },
            cuts={
                mode: {
                    c.key: PeerCut(
                        mode=mode,
                        key=c.key,
                        label=c.label,
                        sample_size=c.sample_size,
                        multi_site=c.multi_site,
                        b2b=c.b2b,
                        anchors=anchors.get((c.mode, c.key), {}),
                    )
                    for c in cut_rows
                    if _mode(c.mode) == mode
                }
                for mode in _MODES
            },
        )

    async def save_peer_cut(self, cut: PeerCut, *, edited_by: str) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(BenchmarkPeerCut)
            .where(BenchmarkPeerCut.mode == cut.mode, BenchmarkPeerCut.key == cut.key)
            .values(
                sample_size=cut.sample_size,
                multi_site=cut.multi_site,
                b2b=cut.b2b,
                updated_by=edited_by,
                updated_at=now,
            )
        )
        for metric, (p10, p25, p50, p75, p90) in cut.anchors.items():
            values = {"p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90}
            statement = insert(BenchmarkAnchor).values(
                mode=cut.mode,
                peer_key=cut.key,
                metric=metric,
                updated_by=edited_by,
                updated_at=now,
                **values,
            )
            await self._session.execute(
                statement.on_conflict_do_update(
                    index_elements=["mode", "peer_key", "metric"],
                    set_={**values, "updated_by": edited_by, "updated_at": now},
                    # Untouched anchors keep their original editor and timestamp.
                    where=(
                        (BenchmarkAnchor.p10 != p10)
                        | (BenchmarkAnchor.p25 != p25)
                        | (BenchmarkAnchor.p50 != p50)
                        | (BenchmarkAnchor.p75 != p75)
                        | (BenchmarkAnchor.p90 != p90)
                    ),
                )
            )

    async def save_band(self, band: Band, *, edited_by: str) -> None:
        await self._session.execute(
            update(BenchmarkBand)
            .where(BenchmarkBand.id == band.id)
            .values(
                label=band.label,
                max_usd=band.max_usd,
                ebitda_adj=band.ebitda_adj,
                rev_emp_mult=band.rev_emp_mult,
                rent_mult=band.rent_mult,
                updated_by=edited_by,
                updated_at=datetime.now(UTC),
            )
        )

    async def save_weights(self, mode: Mode, weights: Mapping[str, int], *, edited_by: str) -> None:
        now = datetime.now(UTC)
        for key, weight in weights.items():
            await self._session.execute(
                update(BenchmarkMetric)
                .where(
                    BenchmarkMetric.mode == mode,
                    BenchmarkMetric.key == key,
                    BenchmarkMetric.weight != weight,
                )
                .values(weight=weight, updated_by=edited_by, updated_at=now)
            )

    async def bump_version(self, *, edited_by: str) -> int:
        row = await self._session.get_one(BenchmarkDatasetVersion, 1, with_for_update=True)
        row.version += 1
        row.updated_by = edited_by
        row.updated_at = datetime.now(UTC)
        return row.version
