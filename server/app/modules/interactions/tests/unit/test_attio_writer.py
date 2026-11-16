import pytest

from app.modules.attio import AttioError
from app.modules.attio.providers.attio import options
from app.modules.interactions.application.ports.attio_writer import (
    RecordGoneError,
    WritesNotAllowedError,
)
from app.modules.interactions.domain.attio_fields import AttioObject, FieldValue
from app.modules.interactions.providers.attio_writer import AttioRecordWriter


class _Client:
    def __init__(self) -> None:
        self.patches: list[tuple[str, dict]] = []
        self.option_reads = 0

    async def get(self, path: str) -> dict:
        self.option_reads += 1
        return {
            "data": [
                {"id": {"option_id": "opt-strong"}, "title": "Strong", "is_archived": False},
                {"id": {"option_id": "opt-old"}, "title": "Weak", "is_archived": True},
            ]
        }

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patches.append((path, json_body))
        return {}

    async def post(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used")

    async def delete(self, path: str) -> None:
        raise AssertionError("not used")

    async def put(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used")


class _Time:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def _fresh_option_cache() -> None:
    options._cache.clear()


def _writer(client: _Client, time: _Time | None = None, *, is_test: bool = False):
    t = time or _Time()
    return AttioRecordWriter(client, 4.0, lambda: is_test, t.clock, t.sleep)


async def test_each_field_kind_is_sent_in_the_shape_attio_expects() -> None:
    client = _Client()

    await _writer(client).patch(
        AttioObject.ORGANIZATIONS,
        "rec-1",
        [
            FieldValue("last_interaction_at", "2026-11-12T10:00:00.000+00:00"),
            FieldValue("last_interaction_subject", "Board call"),
            FieldValue("connection_strength", "Strong"),
            FieldValue("last_interaction_owner", "member-1"),
        ],
    )

    ((path, body),) = client.patches
    assert path == "/objects/organizations/records/rec-1"
    assert body == {
        "data": {
            "values": {
                "last_interaction_at": [{"value": "2026-11-12T10:00:00.000+00:00"}],
                "last_interaction_subject": [{"value": "Board call"}],
                "connection_strength": [{"option": "opt-strong"}],
                "last_interaction_owner": [
                    {"referenced_actor_type": "workspace-member", "referenced_actor_id": "member-1"}
                ],
            }
        }
    }


async def test_requests_are_spaced_to_the_configured_rate() -> None:
    client, time = _Client(), _Time()
    writer = _writer(client, time)
    field = [FieldValue("last_interaction_subject", "x")]

    for _ in range(3):
        await writer.patch(AttioObject.PERSON, "rec", field)

    # 4 a second means 0.25s between requests; the first goes straight out.
    assert time.slept == [pytest.approx(0.25), pytest.approx(0.25)]
    assert len(client.patches) == 3


async def test_nothing_is_written_while_the_instance_is_flagged_as_test() -> None:
    client = _Client()

    with pytest.raises(WritesNotAllowedError):
        await _writer(client, is_test=True).patch(
            AttioObject.PERSON, "rec", [FieldValue("last_interaction_subject", "x")]
        )

    assert client.patches == []


class _RejectingClient(_Client):
    def __init__(self, status: int) -> None:
        super().__init__()
        self.status = status

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AttioError(self.status, "rejected")


async def test_a_404_on_the_patch_means_the_record_is_gone() -> None:
    with pytest.raises(RecordGoneError):
        await _writer(_RejectingClient(404)).patch(
            AttioObject.PERSON, "rec", [FieldValue("last_interaction_subject", "x")]
        )


async def test_any_other_attio_error_is_still_an_error() -> None:
    with pytest.raises(AttioError):
        await _writer(_RejectingClient(403)).patch(
            AttioObject.PERSON, "rec", [FieldValue("last_interaction_subject", "x")]
        )


async def test_a_field_that_should_be_empty_is_sent_as_an_empty_list() -> None:
    client = _Client()

    await _writer(client).patch(
        AttioObject.ORGANIZATIONS,
        "rec-1",
        [
            FieldValue("next_interaction_at", None),
            FieldValue("last_interaction_owner", None),
            FieldValue("connection_strength", None),
        ],
    )

    ((_, body),) = client.patches
    assert body == {
        "data": {
            "values": {
                "next_interaction_at": [],
                "last_interaction_owner": [],
                "connection_strength": [],
            }
        }
    }
    assert client.option_reads == 0
