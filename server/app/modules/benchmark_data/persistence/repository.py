"""Postgres adapter for `BenchmarkDataRepository`. Maps rows to domain values;
ORM types never leave this file."""

from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import RootModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_data import BenchmarkPeerCut, BenchmarkRule
from app.modules.benchmark_data.domain.dataset import (
    Anchors,
    Band,
    BenchmarkDataset,
    Editor,
    Metric,
    Mode,
    PeerCut,
)

_MODES: tuple[Mode, ...] = ("sme", "tech")


class AnchorSet(RootModel[dict[str, Anchors]]):
    """The `anchors` JSON: metric key to [p10, p25, p50, p75, p90]."""


def _mode(value: str | None) -> Mode:
    if value == "sme":
        return "sme"
    if value == "tech":
        return "tech"
    raise ValueError(f"Unknown benchmark mode {value!r}")


def _num(value: object) -> float:
    if value is None:
        raise ValueError("Missing a required benchmark number")
    return float(str(value))


def _band(row: BenchmarkRule) -> Band:
    return Band(
        id=row.id,
        code=row.code,
        label=row.label,
        max_usd=None if row.max_usd is None else float(row.max_usd),
        ebitda_adj=_num(row.ebitda_adj),
        rev_emp_mult=_num(row.rev_emp_mult),
        rent_mult=_num(row.rent_mult),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        updated_by_name=row.updated_by_name,
    )


def _metric(row: BenchmarkRule) -> Metric:
    if row.unit is None or row.higher_is_better is None or row.weight is None:
        raise ValueError(f"Metric rule {row.code} is missing its columns")
    return Metric(
        id=row.id,
        key=row.code,
        label=row.label,
        unit=row.unit,
        higher_is_better=row.higher_is_better,
        weight=row.weight,
        observed=row.observed,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        updated_by_name=row.updated_by_name,
    )


def _cut(row: BenchmarkPeerCut) -> PeerCut:
    return PeerCut(
        id=row.id,
        mode=_mode(row.mode),
        key=row.key,
        label=row.label,
        sample_size=row.sample_size,
        multi_site=row.multi_site,
        b2b=row.b2b,
        anchors=AnchorSet.model_validate(row.anchors).root,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        updated_by_name=row.updated_by_name,
    )


class PostgresBenchmarkDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, *, for_update: bool = False) -> BenchmarkDataset:
        rules_query = select(BenchmarkRule).order_by(
            BenchmarkRule.kind, BenchmarkRule.mode, BenchmarkRule.position
        )
        cuts_query = select(BenchmarkPeerCut).order_by(BenchmarkPeerCut.mode, BenchmarkPeerCut.key)
        if for_update:
            rules_query, cuts_query = rules_query.with_for_update(), cuts_query.with_for_update()
        rules = (await self._session.scalars(rules_query)).all()
        cuts = (await self._session.scalars(cuts_query)).all()
        stamps = [r.updated_at for r in rules] + [c.updated_at for c in cuts]
        return BenchmarkDataset(
            updated_at=max(stamps),
            bands=tuple(_band(r) for r in rules if r.kind == "band"),
            metrics={
                mode: {r.code: _metric(r) for r in rules if r.kind == "metric" and r.mode == mode}
                for mode in _MODES
            },
            cuts={mode: {c.key: _cut(c) for c in cuts if c.mode == mode} for mode in _MODES},
        )

    async def save_peer_cut(self, cut: PeerCut, *, editor: Editor) -> PeerCut:
        result = await self._session.execute(
            update(BenchmarkPeerCut)
            .where(BenchmarkPeerCut.id == cut.id)
            .values(
                sample_size=cut.sample_size,
                multi_site=cut.multi_site,
                b2b=cut.b2b,
                anchors=AnchorSet(dict(cut.anchors)).model_dump(mode="json"),
                updated_by=editor.slack_user_id,
                updated_by_name=editor.name,
                updated_at=datetime.now(UTC),
            )
            .returning(BenchmarkPeerCut)
        )
        return _cut(result.scalar_one())

    async def save_band(self, band: Band, *, editor: Editor) -> Band:
        result = await self._session.execute(
            update(BenchmarkRule)
            .where(BenchmarkRule.id == band.id)
            .values(
                label=band.label,
                max_usd=band.max_usd,
                ebitda_adj=band.ebitda_adj,
                rev_emp_mult=band.rev_emp_mult,
                rent_mult=band.rent_mult,
                updated_by=editor.slack_user_id,
                updated_by_name=editor.name,
                updated_at=datetime.now(UTC),
            )
            .returning(BenchmarkRule)
        )
        return _band(result.scalar_one())

    async def save_weights(
        self, mode: Mode, weights: Mapping[str, int], *, editor: Editor
    ) -> Mapping[str, Metric]:
        now = datetime.now(UTC)
        for key, weight in weights.items():
            await self._session.execute(
                update(BenchmarkRule)
                .where(
                    BenchmarkRule.kind == "metric",
                    BenchmarkRule.mode == mode,
                    BenchmarkRule.code == key,
                    BenchmarkRule.weight != weight,
                )
                .values(
                    weight=weight,
                    updated_by=editor.slack_user_id,
                    updated_by_name=editor.name,
                    updated_at=now,
                )
            )
        rows = await self._session.scalars(
            select(BenchmarkRule)
            .where(BenchmarkRule.kind == "metric", BenchmarkRule.mode == mode)
            .order_by(BenchmarkRule.position)
        )
        return {row.code: _metric(row) for row in rows}
