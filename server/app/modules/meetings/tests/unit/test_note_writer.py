"""`AttioNoteWriter` stamps `is_test` on every note it files.

One SOURCE Attio workspace serves both environments, and a note written
without the flag is invisible in the UI of both — Attio's checkbox filter
offers only "is true" and "is false", never "is empty".
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.modules.meetings import bootstrap
from app.modules.meetings.providers.attio.note_writer import AttioNoteWriter


class _FakeClient:
    def __init__(self, response: dict | None = None) -> None:
        self.post_calls: list[tuple[str, dict]] = []
        self._response = response or {
            "data": {"id": {"record_id": "3f1d2c4e-0000-4000-8000-000000000001"}}
        }

    async def post(self, path: str, json_body: dict) -> dict:
        self.post_calls.append((path, json_body))
        return self._response


async def _push(writer: AttioNoteWriter) -> UUID | None:
    return await writer.push_note(
        organization_attio_id="org-1",
        content="Met the founder.",
        created_at=datetime(2026, 9, 7, tzinfo=UTC),
    )


@pytest.mark.parametrize("is_test", [True, False])
async def test_push_note_stamps_the_scope(is_test: bool) -> None:
    client = _FakeClient()

    await _push(AttioNoteWriter(client, is_test=is_test))

    _, body = client.post_calls[0]
    assert body["data"]["values"]["is_test"] is is_test


async def test_push_note_still_swallows_attio_failures() -> None:
    """Unchanged contract: a broken Attio integration must never fail the
    caller's meeting."""

    class _Failing:
        async def post(self, path: str, json_body: dict) -> dict:
            raise RuntimeError("attio is down")

    assert await _push(AttioNoteWriter(_Failing(), is_test=False)) is None


def test_build_note_writer_always_returns_a_writer() -> None:
    """The old gate returned `None` when `ATTIO_NOTE_OBJECT_SLUG` was unset,
    because the `note` object existed only in SOURCE. With one workspace
    serving both environments there is no such deployment left, and keeping
    the gate would mean note pushes silently stopping on a blank setting."""
    assert isinstance(bootstrap.build_note_writer(), AttioNoteWriter)
