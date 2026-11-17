from collections.abc import Mapping, Sequence

from app.modules.interactions.application.attio_seed import AttioSeedService
from app.modules.interactions.application.ports.seed_source import SeedRead
from app.modules.interactions.application.ports.sent_values import RecordValues, SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject
from app.modules.interactions.providers.attio_seed_source import AttioSeedSource


def _ts(value: str) -> list[dict]:
    return [{"value": value, "active_until": None}]


def _interaction(when: str) -> list[dict]:
    return [{"interaction_type": "email", "interacted_at": when, "active_until": None}]


ORG = {
    "id": {"record_id": "org-1"},
    "values": {
        "is_test": [{"value": False, "active_until": None}],
        "legacy_attio_id": [{"value": "co-1", "active_until": None}],
        "connection_strength": [{"option": {"title": "Weak"}, "active_until": None}],
        "last_interaction_at": _ts("2026-02-23T08:00:23.000000000Z"),
    },
}
TEST_ORG = {
    "id": {"record_id": "org-test"},
    "values": {
        "is_test": [{"value": True, "active_until": None}],
        "connection_strength": [{"option": {"title": "Strong"}, "active_until": None}],
    },
}
EMPTY_ORG = {
    "id": {"record_id": "org-empty"},
    "values": {"is_test": [{"value": False, "active_until": None}]},
}
COMPANY = {
    "id": {"record_id": "co-1"},
    "values": {
        "first_interaction": _interaction("2024-05-01T10:00:00.000000000Z"),
        "last_interaction": _interaction("2026-09-01T10:00:00.000000000Z"),
        "strongest_connection_user": [
            {"referenced_actor_type": "workspace-member", "referenced_actor_id": "m-hugo"}
        ],
    },
}


class _Client:
    def __init__(self, pages: Mapping[str, list[dict]]) -> None:
        self._pages = pages

    async def post(self, path: str, json_body: dict) -> dict:
        slug = path.split("/")[2]
        return {"data": self._pages.get(slug, []) if json_body["offset"] == 0 else []}

    async def get(self, path: str) -> dict:
        raise AssertionError("not used")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("the seed must never write to Attio")

    async def delete(self, path: str) -> None:
        raise AssertionError("not used")

    async def put(self, path: str, json_body: dict) -> dict:
        raise AssertionError("the seed must never write to Attio")


async def _rows(pages: Mapping[str, list[dict]]) -> Sequence[SeedRow]:
    source = AttioSeedSource(_Client(pages), owns=lambda is_test: not is_test)
    return (await source.read(AttioObject.ORGANIZATIONS)).rows


async def test_the_seed_stores_what_the_record_holds_and_the_live_company_value() -> None:
    rows = {
        (r.field): (r.value, r.baseline)
        for r in await _rows({"organizations": [ORG], "companies": [COMPANY]})
    }

    assert rows["connection_strength"] == ("Weak", None)
    assert rows["last_interaction_at"] == (
        "2026-02-23T08:00:23.000+00:00",
        "2026-09-01T10:00:00.000+00:00",
    )
    assert rows["first_interaction_at"] == (None, "2024-05-01T10:00:00.000+00:00")
    assert rows["strongest_connection_user"] == (None, "m-hugo")


async def test_test_records_and_records_with_nothing_in_them_are_not_seeded() -> None:
    rows = await _rows({"organizations": [TEST_ORG, EMPTY_ORG], "companies": []})

    assert rows == []


async def test_a_record_with_no_matching_company_still_keeps_its_own_values() -> None:
    org = {**ORG, "values": {**ORG["values"], "legacy_attio_id": _ts("unknown")}}

    rows = await _rows({"organizations": [org], "companies": [COMPANY]})

    assert {r.field for r in rows} == {"connection_strength", "last_interaction_at"}
    assert all(r.baseline is None for r in rows)


class _Source:
    async def read(self, obj: AttioObject) -> SeedRead:
        return SeedRead([SeedRow(f"{obj.value}-1", "connection_strength", "Weak", None)], 1)


class _Sent:
    def __init__(self) -> None:
        self.seeded: list[AttioObject] = []
        self.marked: list[AttioObject] = []

    async def load(self, obj: AttioObject) -> Mapping[str, RecordValues]:
        return {}

    async def save(self, obj: AttioObject, record_id: str, fields: Mapping[str, str]) -> None:
        raise AssertionError("the seed only seeds")

    async def seed(self, obj: AttioObject, rows: Sequence[SeedRow]) -> int:
        self.seeded.append(obj)
        return len(rows)

    async def is_seeded(self, obj: AttioObject) -> bool:
        return obj in self.marked

    async def mark_seeded(self, obj: AttioObject) -> None:
        self.marked.append(obj)


async def test_the_service_seeds_every_object_and_marks_each_complete() -> None:
    sent = _Sent()

    reports = await AttioSeedService(_Source(), sent).run()

    assert [(r.object, r.rows_read, r.rows_stored) for r in reports] == [
        (AttioObject.ORGANIZATIONS, 1, 1),
        (AttioObject.PERSON, 1, 1),
        (AttioObject.DEAL, 1, 1),
    ]
    assert sent.marked == sent.seeded == list(AttioObject)


class _EmptySource:
    async def read(self, obj: AttioObject) -> SeedRead:
        return SeedRead([], 0)


async def test_a_seed_that_read_nothing_is_not_marked_done() -> None:
    sent = _Sent()

    reports = await AttioSeedService(_EmptySource(), sent).run()

    assert sent.marked == []
    assert [r.rows_read for r in reports] == [0, 0, 0]
    assert [r.marked for r in reports] == [False, False, False]


class _RecordsButNoValuesSource:
    async def read(self, obj: AttioObject) -> SeedRead:
        return SeedRead([], 3)


async def test_an_object_whose_records_hold_nothing_yet_is_still_marked_done() -> None:
    # A Deal starts with none of the rollup fields filled, so there is nothing to store.
    sent = _Sent()

    reports = await AttioSeedService(_RecordsButNoValuesSource(), sent).run()

    assert sent.marked == list(AttioObject)
    assert [r.rows_stored for r in reports] == [0, 0, 0]
    assert [(r.records_read, r.marked) for r in reports] == [(3, True)] * 3


DEAL = {
    "id": {"record_id": "deal-1"},
    "values": {
        "last_interaction_at": _ts("2026-10-01T08:00:00.000000000Z"),
        "connection_strength": [{"option": {"title": "Good"}, "active_until": None}],
        "first_interaction_at": _ts("2026-01-01T00:00:00.000000000Z"),
    },
}


async def test_a_deal_is_seeded_from_its_own_five_fields_with_no_baseline() -> None:
    pages = {"deal": [DEAL, {"id": {"record_id": "deal-2"}, "values": {}}]}
    source = AttioSeedSource(_Client(pages), owns=lambda is_test: not is_test)

    read = await source.read(AttioObject.DEAL)

    assert read.records == 2
    assert {(r.record_id, r.field, r.baseline) for r in read.rows} == {
        ("deal-1", "last_interaction_at", None),
        ("deal-1", "connection_strength", None),
    }
