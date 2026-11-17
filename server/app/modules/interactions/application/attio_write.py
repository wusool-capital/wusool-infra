"""One write round: compute each record's fields and send only what changed to Attio."""

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.modules.interactions.application.ports.attio_writer import (
    AttioWriterPort,
    RecordGoneError,
    WritesNotAllowedError,
)
from app.modules.interactions.application.ports.deal_parties import DealPartiesPort
from app.modules.interactions.application.ports.score_store import ScoreStorePort
from app.modules.interactions.application.ports.sent_values import RecordValues, SentValuesPort
from app.modules.interactions.application.ports.touch_reader import TouchReaderPort
from app.modules.interactions.domain.attio_fields import (
    AttioObject,
    FieldMap,
    WriteMode,
    fields_for,
    fields_of,
    plan_record,
)
from app.modules.interactions.domain.deals import DealParties, deal_touches
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
    # The Deal rollup has its own switch, so it can be tried while Organizations and Person run.
    deal_mode: WriteMode = WriteMode.OFF
    max_deals_per_round: int = 500


@dataclass(frozen=True)
class WriteReport:
    patched: int = 0
    fields: int = 0
    cleared: int = 0
    failed: int = 0
    gone: int = 0
    scores_updated: int = 0
    # Deals written, counted among `patched` as well.
    deals: int = 0
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
        deals: DealPartiesPort | None = None,
    ) -> None:
        self._deals = deals
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
        touched: dict[AttioObject, Mapping[str, tuple[Touch, ...]]] = {}
        for obj, touches_of in (
            (AttioObject.ORGANIZATIONS, self._reader.touches_by_organization),
            (AttioObject.PERSON, self._reader.touches_by_person),
        ):
            if not await self._sent.is_seeded(obj):
                report = replace(report, unseeded=(*report.unseeded, obj))
                continue
            touched[obj] = await touches_of()
            report = await self._round_for(
                obj,
                touched[obj],
                members,
                read_ids,
                report,
                dry_run=self._config.dry_run,
                cap=self._config.max_records_per_round,
            )
        if self._deals is not None and self._config.deal_mode is not WriteMode.OFF:
            report = await self._deal_round(self._deals, touched, members, read_ids, report)
        return report

    async def _deal_round(
        self,
        deals_port: DealPartiesPort,
        touched: Mapping[AttioObject, Mapping[str, tuple[Touch, ...]]],
        members: Mapping[str, str],
        read_ids: frozenset[str],
        report: WriteReport,
    ) -> WriteReport:
        if not await self._sent.is_seeded(AttioObject.DEAL):
            return replace(report, unseeded=(*report.unseeded, AttioObject.DEAL))
        deals = await deals_port.load()
        touches = deal_touches(
            deals,
            touched.get(AttioObject.ORGANIZATIONS, {}),
            touched.get(AttioObject.PERSON, {}),
        )
        orgs = await self._sent.load(AttioObject.ORGANIZATIONS)
        people = await self._sent.load(AttioObject.PERSON)
        baselines = {d.deal_id: _party_baseline(d, orgs, people, read_ids) for d in deals}
        return await self._round_for(
            AttioObject.DEAL,
            touches,
            members,
            read_ids,
            report,
            dry_run=self._config.dry_run or self._config.deal_mode is WriteMode.DRY_RUN,
            cap=self._config.max_deals_per_round,
            baselines=baselines,
        )

    async def _round_for(
        self,
        obj: AttioObject,
        touches: Mapping[str, tuple[Touch, ...]],
        members: Mapping[str, str],
        read_ids: frozenset[str],
        report: WriteReport,
        *,
        dry_run: bool,
        cap: int,
        baselines: Mapping[str, FieldMap] | None = None,
    ) -> WriteReport:
        stored = await self._sent.load(obj)
        # Only Organizations and Person have a score column; a Deal's strength has no number.
        uses_scores = obj is not AttioObject.DEAL
        current_scores = await self._scores.load(obj) if uses_scores else {}
        now = self._clock()
        start = report.patched + report.failed + report.gone
        new_scores: dict[str, Decimal] = {}
        # A record that went quiet has no touches but still needs its decay and next dates.
        for record_id in sorted(set(touches) | set(stored)):
            # A dry run sees everything; a real round is capped, counting failed attempts.
            attempts = report.patched + report.failed + report.gone - start
            if not dry_run and attempts >= cap:
                report = replace(report, hit_cap=True)
                break
            summary = summarize(touches.get(record_id, ()), now, self._config.rules)
            values = stored.get(record_id, RecordValues({}, {}))
            baseline = baselines.get(record_id, values.baseline) if baselines else values.baseline
            plan = plan_record(
                fields_for(summary, members), values.sent, baseline, read_ids, fields_of(obj)
            )
            if plan.writes and not dry_run:
                try:
                    await self._writer.patch(obj, record_id, plan.writes)
                    await self._sent.save(obj, record_id, {w.slug: w.value for w in plan.writes})
                except WritesNotAllowedError:
                    raise
                except RecordGoneError:
                    # Gone from Attio is not an outage; it must not keep the stale-sync alarm on.
                    logger.warning(
                        "interactions_attio_record_gone object=%s record=%s", obj.value, record_id
                    )
                    report = replace(report, gone=report.gone + 1)
                    continue
                except Exception:
                    # One bad record must not stop the round; it is retried next round.
                    logger.exception("interactions_attio_write_failed object=%s", obj.value)
                    report = replace(report, failed=report.failed + 1)
                    continue
            if plan.writes:
                report = replace(
                    report,
                    patched=report.patched + 1,
                    fields=report.fields + len(plan.writes),
                    cleared=report.cleared + sum(1 for w in plan.writes if w.value is None),
                    deals=report.deals + int(obj is AttioObject.DEAL),
                )
            # The score tracks the label: left alone for an unread mailbox, absent without one.
            score = Decimal(str(round(summary.score, _SCORE_PLACES)))
            if (
                uses_scores
                and not plan.skip_strength
                and plan.has_strength
                and record_id in current_scores
                and _moved(current_scores[record_id], score)
            ):
                new_scores[record_id] = score
        if new_scores and not dry_run:
            try:
                await self._scores.save(obj, new_scores)
                # Counted here: a bulk update reports its row count as unknown (-1).
                report = replace(report, scores_updated=report.scores_updated + len(new_scores))
            except Exception:
                logger.exception("interactions_score_write_failed object=%s", obj.value)
        return report


def _moved(old: Decimal | None, new: Decimal) -> bool:
    if old is None:
        return True
    return abs(new - old) >= max(_MIN_MOVE, abs(old) * _MIN_MOVE_RATIO)


def _party_baseline(
    deal: DealParties,
    organizations: Mapping[str, RecordValues],
    people: Mapping[str, RecordValues],
    read_ids: frozenset[str],
) -> FieldMap:
    """A Deal has no baseline of its own. If its buyer or seller was last led by a mailbox we
    don't read, say so, so the Deal's strength is left alone as theirs is."""
    for stored, record_id in (
        (organizations, deal.seller_organization_id),
        (organizations, deal.buyer_organization_id),
        (people, deal.buyer_person_id),
    ):
        values = stored.get(record_id) if record_id else None
        user = values.baseline.get("strongest_connection_user") if values else None
        if user is not None and user not in read_ids:
            return {"strongest_connection_user": user}
    return {}
