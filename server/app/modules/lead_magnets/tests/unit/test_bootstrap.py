"""`run_sweeper_forever`'s loop behaviour: a failed pass must not kill the
loop, and cancellation (how `main.py`'s lifespan stops it on shutdown) must
actually propagate rather than being swallowed.
"""

import asyncio

import pytest

from app.modules.lead_magnets import bootstrap


class _FakeSettings:
    lead_magnet_sweeper_interval_s = 0
    lead_magnet_sweeper_stale_after_s = 300


class _FakeSessionCtx:
    async def __aenter__(self):
        class _Session:
            async def commit(self) -> None:
                pass

        return _Session()

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def test_loop_survives_a_failed_pass_and_stops_on_cancel(monkeypatch) -> None:
    calls: list[int] = []

    async def fake_sweep_once(tool_runs, submissions, *, stale_after_s):
        calls.append(stale_after_s)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(bootstrap, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(bootstrap, "get_sessionmaker", lambda: _FakeSessionCtx)
    monkeypatch.setattr(bootstrap, "build_tool_runs", lambda session: object())
    monkeypatch.setattr(bootstrap, "build_submission_service", lambda session: object())
    monkeypatch.setattr(bootstrap, "sweep_once", fake_sweep_once)

    task = asyncio.create_task(bootstrap.run_sweeper_forever())
    for _ in range(1000):
        if len(calls) >= 3:
            break
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 3, "a RuntimeError on one pass must not stop later passes"
