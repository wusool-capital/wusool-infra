from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.interactions.application.attio_write import AttioWriteConfig, AttioWriteService
from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.application.ports.sent_values import RecordValues, SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject, FieldValue
from app.modules.interactions.domain.model import Channel, ScoringRules, Touch
from app.modules.interactions.tests.fakes.touches import JULES, NOW, SARA

ORG = AttioObject.ORGANIZATIONS


class _Reader:
    def __init__(
        self,
        by_org: Mapping[str, tuple[Touch, ...]],
        by_person: Mapping[str, tuple[Touch, ...]] | None = None,
    ) -> None:
        self._by_org = by_org
        self._by_person = by_person or {}

    async def touches_by_organization(self) -> Mapping[str, tuple[Touch, ...]]:
        return self._by_org

    async def touches_by_person(self) -> Mapping[str, tuple[Touch, ...]]:
        return self._by_person


class _Sent:
    def __init__(self, seeded: set[AttioObject], stored: Mapping[str, RecordValues] | None = None):
        self.seeded = seeded
        self.stored = dict(stored or {})
        self.events: list[str] = []

    async def load(self, obj: AttioObject) -> Mapping[str, RecordValues]:
        return self.stored if obj is ORG else {}

    async def save(self, obj: AttioObject, record_id: str, fields: Mapping[str, str]) -> None:
        self.events.append(f"save {record_id}")
        old = self.stored.get(record_id, RecordValues({}, {}))
        self.stored[record_id] = RecordValues({**old.sent, **fields}, old.baseline)

    async def seed(self, obj: AttioObject, rows: Sequence[SeedRow]) -> int:
        return 0

    async def is_seeded(self, obj: AttioObject) -> bool:
        return obj in self.seeded

    async def mark_seeded(self, obj: AttioObject) -> None:
        self.seeded.add(obj)


class _Scores:
    """Scores as the mirror holds them; `rows` are the records it has."""

    def __init__(self, rows: Mapping[str, Decimal | None] | None = None) -> None:
        self.rows = dict(rows or {})
        self.saved: dict[str, Decimal] = {}

    async def load(self, obj: AttioObject) -> Mapping[str, Decimal | None]:
        return self.rows if obj is ORG else {}

    async def save(self, obj: AttioObject, scores: Mapping[str, Decimal]) -> int:
        self.saved.update(scores)
        return len(scores)


class _Writer:
    def __init__(self, sent: _Sent, fail_for: str | None = None, refuse: bool = False) -> None:
        self.sent = sent
        self.fail_for = fail_for
        self.refuse = refuse
        self.patches: list[tuple[str, dict[str, str | None]]] = []

    async def patch(self, obj: AttioObject, record_id: str, fields: Sequence[FieldValue]) -> None:
        if self.refuse:
            raise WritesNotAllowedError("test instance")
        if record_id == self.fail_for:
            raise RuntimeError("attio said no")
        self.sent.events.append(f"patch {record_id}")
        self.patches.append((record_id, {f.slug: f.value for f in fields}))


def _touches(count: int = 2) -> tuple[Touch, ...]:
    return tuple(
        Touch(f"m{i}", JULES, SARA, Channel.MEETING, None, NOW - timedelta(days=1 + i))
        for i in range(count)
    )


async def _members() -> Mapping[str, str]:
    return {JULES: "m-jules"}


def _service(
    sent: _Sent,
    writer: _Writer,
    by_org: Mapping[str, tuple[Touch, ...]],
    *,
    dry_run: bool = False,
    cap: int = 100,
    by_person: Mapping[str, tuple[Touch, ...]] | None = None,
    scores: _Scores | None = None,
) -> AttioWriteService:
    config = AttioWriteConfig(frozenset({JULES}), ScoringRules(), cap, dry_run)
    return AttioWriteService(
        _Reader(by_org, by_person), sent, writer, scores or _Scores(), _members, config, lambda: NOW
    )


async def test_nothing_is_written_for_an_object_that_has_not_been_seeded() -> None:
    sent = _Sent(seeded=set())
    writer = _Writer(sent)

    report = await _service(sent, writer, {"o1": _touches()}).run_round()

    assert writer.patches == []
    assert set(report.unseeded) == {AttioObject.ORGANIZATIONS, AttioObject.PERSON}


async def test_a_new_record_gets_its_fields_and_the_send_is_recorded_after_attio_has_it() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent)

    report = await _service(sent, writer, {"o1": _touches()}).run_round()

    ((record, values),) = writer.patches
    assert record == "o1"
    assert {"last_interaction_at", "connection_strength", "last_interaction_channel"} <= set(values)
    assert values["last_interaction_channel"] == "Meeting"
    assert sent.events == ["patch o1", "save o1"]
    assert report.patched == 1 and report.failed == 0


async def test_a_second_round_with_nothing_new_writes_nothing() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent)
    service = _service(sent, writer, {"o1": _touches()})
    await service.run_round()

    second = await service.run_round()

    assert len(writer.patches) == 1
    assert second.patched == 0


async def test_a_dry_run_counts_what_it_would_send_and_sends_and_saves_nothing() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent)

    report = await _service(sent, writer, {"o1": _touches()}, dry_run=True).run_round()

    assert (report.patched > 0, writer.patches, sent.events) == (True, [], [])


async def test_one_failing_record_is_skipped_unsaved_and_the_rest_continue() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent, fail_for="o1")

    report = await _service(sent, writer, {"o1": _touches(), "o2": _touches(3)}).run_round()

    assert [r for r, _ in writer.patches] == ["o2"]
    assert (report.patched, report.failed) == (1, 1)
    assert "o1" not in sent.stored


async def test_a_refusal_to_write_stops_the_whole_round() -> None:
    sent = _Sent(seeded={ORG})

    with pytest.raises(WritesNotAllowedError):
        await _service(sent, _Writer(sent, refuse=True), {"o1": _touches()}).run_round()


async def test_the_round_stops_at_the_cap_and_says_so() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent)

    report = await _service(
        sent, writer, {"o1": _touches(), "o2": _touches(), "o3": _touches()}, cap=2
    ).run_round()

    assert (report.patched, report.hit_cap) == (2, True)


async def test_a_record_that_went_quiet_is_visited_and_its_passed_next_date_is_cleared() -> None:
    stored = {
        "o1": RecordValues({"next_interaction_at": "2026-12-01T00:00:00.000+00:00"}, {}),
    }
    sent = _Sent(seeded={ORG}, stored=stored)
    writer = _Writer(sent)

    report = await _service(sent, writer, {}).run_round()

    assert writer.patches == [("o1", {"next_interaction_at": None})]
    assert (report.patched, report.cleared) == (1, 1)
    assert sent.stored["o1"].sent["next_interaction_at"] is None


async def test_strength_is_not_sent_where_attios_strongest_user_is_an_unread_mailbox() -> None:
    stored = {"o1": RecordValues({}, {"strongest_connection_user": "m-hugo"})}
    sent = _Sent(seeded={ORG}, stored=stored)
    writer = _Writer(sent)

    await _service(sent, writer, {"o1": _touches()}).run_round()

    ((_, values),) = writer.patches
    assert "connection_strength" not in values
    assert "last_interaction_at" in values


async def test_a_backlog_of_organizations_does_not_starve_person() -> None:
    sent = _Sent(seeded={ORG, AttioObject.PERSON})
    writer = _Writer(sent)

    report = await _service(
        sent,
        writer,
        {"o1": _touches(), "o2": _touches(), "o3": _touches()},
        cap=1,
        by_person={"p1": _touches(), "p2": _touches()},
    ).run_round()

    assert (report.patched, report.hit_cap) == (2, True)
    assert sorted(r for r, _ in writer.patches) == ["o1", "p1"]


async def test_failed_attempts_count_toward_the_cap() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent, fail_for="o1")

    report = await _service(sent, writer, {"o1": _touches(), "o2": _touches()}, cap=1).run_round()

    assert (report.failed, report.patched, report.hit_cap) == (1, 0, True)


async def test_a_dry_run_looks_at_every_record_whatever_the_cap() -> None:
    sent = _Sent(seeded={ORG})
    writer = _Writer(sent)

    report = await _service(
        sent, writer, {"o1": _touches(), "o2": _touches(), "o3": _touches()}, dry_run=True, cap=1
    ).run_round()

    assert (report.patched, report.hit_cap, writer.patches) == (3, False, [])


async def test_the_score_is_stored_for_records_the_mirror_holds_and_only_when_it_changed() -> None:
    sent = _Sent(seeded={ORG})
    scores = _Scores({"o1": None, "o2": Decimal("0")})

    report = await _service(
        sent, _Writer(sent), {"o1": _touches(), "o2": _touches(), "gone": _touches()}, scores=scores
    ).run_round()

    assert set(scores.saved) == {"o1", "o2"}
    assert scores.saved["o1"] > 0
    assert report.scores_updated == 2


async def test_a_second_round_does_not_rewrite_an_unchanged_score() -> None:
    sent = _Sent(seeded={ORG})
    scores = _Scores({"o1": None})
    service = _service(sent, _Writer(sent), {"o1": _touches()}, scores=scores)
    await service.run_round()
    scores.rows.update(scores.saved)
    scores.saved.clear()

    again = await service.run_round()

    assert (scores.saved, again.scores_updated) == ({}, 0)


async def test_the_score_moves_even_when_no_attio_field_changed() -> None:
    sent = _Sent(seeded={ORG})
    scores = _Scores({"o1": Decimal("1")})
    service = _service(sent, _Writer(sent), {"o1": _touches()}, scores=scores)
    await service.run_round()
    scores.rows.update(scores.saved)
    scores.saved.clear()
    scores.rows["o1"] = Decimal("0.5")

    report = await service.run_round()

    assert (report.patched, report.scores_updated) == (0, 1)


async def test_no_score_is_stored_by_a_dry_run_or_where_strength_is_left_alone() -> None:
    stored = {"o1": RecordValues({}, {"strongest_connection_user": "m-hugo"})}
    sent = _Sent(seeded={ORG}, stored=stored)
    scores = _Scores({"o1": None})

    await _service(sent, _Writer(sent), {"o1": _touches()}, scores=scores).run_round()
    assert scores.saved == {}

    sent2, scores2 = _Sent(seeded={ORG}), _Scores({"o2": None})
    await _service(
        sent2, _Writer(sent2), {"o2": _touches()}, dry_run=True, scores=scores2
    ).run_round()
    assert scores2.saved == {}


async def test_a_tiny_decay_is_not_rewritten_but_a_real_move_is() -> None:
    sent = _Sent(seeded={ORG})
    scores = _Scores({"o1": None})
    service = _service(sent, _Writer(sent), {"o1": _touches(3)}, scores=scores)
    await service.run_round()
    stored = scores.saved["o1"]
    scores.rows["o1"] = stored + Decimal("0.001")
    scores.saved.clear()

    drift = await service.run_round()
    scores.rows["o1"] = stored * 2
    moved = await service.run_round()

    assert (drift.scores_updated, moved.scores_updated) == (0, 1)


async def test_a_quiet_record_fades_to_very_weak_and_its_score_follows() -> None:
    stored = {"o1": RecordValues({"connection_strength": "Strong"}, {})}
    sent = _Sent(seeded={ORG}, stored=stored)
    writer = _Writer(sent)
    scores = _Scores({"o1": Decimal("20")})

    report = await _service(sent, writer, {}, scores=scores).run_round()

    assert writer.patches == [("o1", {"connection_strength": "Very weak"})]
    assert scores.saved == {"o1": Decimal("0")}
    assert report.scores_updated == 1
