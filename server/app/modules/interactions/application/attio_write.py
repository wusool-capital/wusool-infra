"""One write round: compute each record's fields and send only what changed to Attio."""

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.modules.interactions.application.ports.attio_writer import (
    AttioWriterPort,
    WritesNotAllowedError,
)
from app.modules.interactions.application.ports.score_store import ScoreStorePort
from app.modules.interactions.application.ports.sent_values import RecordValues, SentValuesPort
from app.modules.interactions.application.ports.touch_reader import TouchReaderPort
from app.modules.interactions.domain.attio_fields import (
    AttioObject,
    fields_for,
    plan_record,
)
from app.modules.interactions.domain.model import ScoringRules, Touch
from app.modules.interactions.domain.summary import summarize

logger = logging.getLogger(__name__)

# Maps a team address to its Attio workspace member id.
MemberIds = Callable[[], Awaitable[Mapping[str, str]]]

_SCORE_PLACES = 4
# A score decays a little every round, so only a move of 1% (at least 0.05) is worth a write.
_MIN_MOVE = Decimal("0.05")
_MIN_MOVE_RATIO = Decimal("0.01")


@dataclass(frozen=True)
class AttioWriteConfig:
    # Folded addresses of the mailboxes we read; strength is sent only for their records.
    read_mailboxes: frozenset[str]
    rules: ScoringRules
    max_records_per_round: int
    dry_run: bool


@dataclass(frozen=True)
class WriteReport:
    patched: int = 0
    fields: int = 0
    clears_skipped: int = 0
    failed: int = 0
    scores_updated: int = 0
    # Objects whose seed has not run; nothing is written for them.
    unseeded: tuple[AttioObject, ...] = ()
    hit_cap: bool = False
    dry_run: bool = False


class AttioWriteService:
    def __init__(
        self,
        reader: TouchReaderPort,
        sent: SentValuesPort,
        writer: AttioWriterPort,
        scores: ScoreStorePort,
        member_ids: MemberIds,
        config: AttioWriteConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self._reader = reader
        self._sent = sent
        self._writer = writer
        self._scores = scores
        self._member_ids = member_ids
        self._config = config
        self._clock = clock

    async def run_round(self) -> WriteReport:
        members = await self._member_ids()
        read_ids = frozenset(members[m] for m in self._config.read_mailboxes if m in members)
        report = WriteReport(dry_run=self._config.dry_run)
        for obj, touches_of in (
            (AttioObject.ORGANIZATIONS, self._reader.touches_by_organization),
            (AttioObject.PERSON, self._reader.touches_by_person),
        ):
            if not await self._sent.is_seeded(obj):
                report = replace(report, unseeded=(*report.unseeded, obj))
                continue
            report = await self._round_for(obj, await touches_of(), members, read_ids, report)
        return report

    async def _round_for(
        self,
        obj: AttioObject,
        touches: Mapping[str, tuple[Touch, ...]],
        members: Mapping[str, str],
        read_ids: frozenset[str],
        report: WriteReport,
    ) -> WriteReport:
        stored = await self._sent.load(obj)
        current_scores = await self._scores.load(obj)
        now = self._clock()
        start = report.patched + report.failed
        new_scores: dict[str, Decimal] = {}
        # A record that went quiet has no touches but still needs its decay and next dates.
        for record_id in sorted(set(touches) | set(stored)):
            # A dry run sees everything; a real round is capped, counting failed attempts.
            attempts = report.patched + report.failed - start
            if not self._config.dry_run and attempts >= self._config.max_records_per_round:
                report = replace(report, hit_cap=True)
                break
            summary = summarize(touches.get(record_id, ()), now, self._config.rules)
            values = stored.get(record_id, RecordValues({}, {}))
            plan = plan_record(fields_for(summary, members), values.sent, values.baseline, read_ids)
            report = replace(report, clears_skipped=report.clears_skipped + plan.clears_skipped)
            if plan.writes and not self._config.dry_run:
                try:
                    await self._writer.patch(obj, record_id, plan.writes)
                    await self._sent.save(obj, record_id, {w.slug: w.value for w in plan.writes})
                except WritesNotAllowedError:
                    raise
                except Exception:
                    # One bad record must not stop the round; it is retried next round.
                    logger.exception("interactions_attio_write_failed object=%s", obj.value)
                    report = replace(report, failed=report.failed + 1)
                    continue
            if plan.writes:
                report = replace(
                    report, patched=report.patched + 1, fields=report.fields + len(plan.writes)
                )
            # The score tracks the label. Where the label is left alone (an unread mailbox, or a
            # quiet record whose label is not cleared yet) the score is left alone too.
            score = Decimal(str(round(summary.score, _SCORE_PLACES)))
            if (
                not plan.skip_strength
                and summary.connection_strength is not None
                and record_id in current_scores
                and _moved(current_scores[record_id], score)
            ):
                new_scores[record_id] = score
        if new_scores and not self._config.dry_run:
            try:
                updated = await self._scores.save(obj, new_scores)
                report = replace(report, scores_updated=report.scores_updated + updated)
            except Exception:
                logger.exception("interactions_score_write_failed object=%s", obj.value)
        return report


def _moved(old: Decimal | None, new: Decimal) -> bool:
    if old is None:
        return True
    return abs(new - old) >= max(_MIN_MOVE, abs(old) * _MIN_MOVE_RATIO)
