from collections.abc import Mapping, Sequence
from datetime import timedelta

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


class _Writer:
    def __init__(self, sent: _Sent, fail_for: str | None = None, refuse: bool = False) -> None:
        self.sent = sent
        self.fail_for = fail_for
        self.refuse = refuse
        self.patches: list[tuple[str, dict[str, str]]] = []

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
) -> AttioWriteService:
    config = AttioWriteConfig(frozenset({JULES}), ScoringRules(), cap, dry_run)
    return AttioWriteService(
        _Reader(by_org, by_person), sent, writer, _members, config, lambda: NOW
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


async def test_a_record_that_went_quiet_is_visited_and_its_lost_next_date_is_counted() -> None:
    stored = {
        "o1": RecordValues({"next_interaction_at": "2026-12-01T00:00:00.000+00:00"}, {}),
    }
    sent = _Sent(seeded={ORG}, stored=stored)
    writer = _Writer(sent)

    report = await _service(sent, writer, {}).run_round()

    assert writer.patches == []
    assert report.clears_skipped == 1


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
