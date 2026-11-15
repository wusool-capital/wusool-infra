"""Reading and editing the benchmark dataset. Every edit is checked against the
dataset it lands in, and each row it changes leaves one `activities` event."""

from collections.abc import Mapping
from uuid import UUID

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivityRecorderPort,
    ActivitySource,
    BenchmarkEditPayload,
    EventType,
    SubjectType,
)
from app.modules.benchmark_data.application.ports.repository import BenchmarkDataRepository
from app.modules.benchmark_data.domain.dataset import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Editor,
    Metric,
    Mode,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
    apply_band_edit,
    apply_peer_cut_edit,
    changed_band_fields,
    changed_peer_cut_fields,
    check_weights,
)

_WEIGHT = ("weight",)


class BenchmarkDataService:
    def __init__(
        self, repository: BenchmarkDataRepository, activities: ActivityRecorderPort
    ) -> None:
        self._repository = repository
        self._activities = activities

    async def dataset(self) -> BenchmarkDataset:
        return await self._repository.load()

    async def edit_peer_cut(
        self, mode: Mode, key: str, edit: PeerCutEdit, *, editor: Editor, source: ActivitySource
    ) -> PeerCut:
        dataset = await self._repository.load(for_update=True)
        cut = dataset.cuts[mode].get(key)
        if cut is None:
            raise UnknownRecordError(f"No {mode} peer cut '{key}'")
        updated = apply_peer_cut_edit(cut, edit, dataset.metrics[mode])
        changed = changed_peer_cut_fields(cut, updated)
        if not changed:
            return cut
        saved = await self._repository.save_peer_cut(updated, edited_by=editor.label)
        await self._record(
            SubjectType.BENCHMARK_PEER_CUT,
            EventType.BENCHMARK_PEER_CUT_EDITED,
            saved.id,
            changed,
            editor,
            source,
        )
        return saved

    async def edit_band(
        self, code: str, edit: BandEdit, *, editor: Editor, source: ActivitySource
    ) -> tuple[Band, ...]:
        dataset = await self._repository.load(for_update=True)
        bands = apply_band_edit(dataset.bands, code, edit)
        before = next(b for b in dataset.bands if b.code == code)
        after = next(b for b in bands if b.code == code)
        changed = changed_band_fields(before, after)
        if not changed:
            return dataset.bands
        saved = await self._repository.save_band(after, edited_by=editor.label)
        await self._record(
            SubjectType.BENCHMARK_RULE,
            EventType.BENCHMARK_RULE_EDITED,
            saved.id,
            changed,
            editor,
            source,
        )
        return tuple(saved if b.code == code else b for b in bands)

    async def set_weights(
        self, mode: Mode, weights: Mapping[str, int], *, editor: Editor, source: ActivitySource
    ) -> Mapping[str, Metric]:
        dataset = await self._repository.load(for_update=True)
        current = dataset.metrics[mode]
        check_weights(current, weights)
        changed = [key for key, weight in weights.items() if current[key].weight != weight]
        if not changed:
            return current
        saved = await self._repository.save_weights(mode, weights, edited_by=editor.label)
        for key in changed:
            await self._record(
                SubjectType.BENCHMARK_RULE,
                EventType.BENCHMARK_RULE_EDITED,
                saved[key].id,
                _WEIGHT,
                editor,
                source,
            )
        return saved

    async def _record(
        self,
        subject_type: SubjectType,
        event_type: EventType,
        row_id: UUID,
        changed_fields: tuple[str, ...],
        editor: Editor,
        source: ActivitySource,
    ) -> None:
        await self._activities.record(
            ActivityEvent(
                subject_type=subject_type,
                event_type=event_type,
                source=source,
                actor=ActivityActor.slack(editor.slack_user_id),
                payload=BenchmarkEditPayload(changed_fields=changed_fields),
                subject_uuid=row_id,
                outcome="succeeded",
            )
        )
