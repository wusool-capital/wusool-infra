"""Coverage for `trigger_seller_discovery`'s idempotency guard — one
discovery search per run, whichever path triggers it (the automatic
below-threshold trigger, or the "Find more sellers" button, which stays
visible/clickable after the automatic trigger already fired).
"""

import uuid

from app.modules.matching_engine.api import dependencies as deps


async def test_second_trigger_for_the_same_run_is_skipped(monkeypatch) -> None:
    calls = 0

    def fake_get_sessionmaker():
        nonlocal calls
        calls += 1
        raise AssertionError("should not reach the DB on a duplicate trigger")

    monkeypatch.setattr(deps, "get_sessionmaker", fake_get_sessionmaker)

    run_id = uuid.uuid4()
    # First call: reaches (and fails inside) the guarded body — proves the
    # guard didn't block a genuinely-first trigger.
    try:
        await deps.trigger_seller_discovery(run_id, channel_id="C_TEST")
    except AssertionError:
        pass

    # Second call, same run_id: must be skipped before ever touching the DB.
    await deps.trigger_seller_discovery(run_id, channel_id="C_TEST")

    assert calls == 1


async def test_different_runs_are_not_deduplicated_against_each_other(monkeypatch) -> None:
    calls = 0

    def fake_get_sessionmaker():
        nonlocal calls
        calls += 1
        raise AssertionError("stop before the DB — only the call count matters here")

    monkeypatch.setattr(deps, "get_sessionmaker", fake_get_sessionmaker)

    for run_id in (uuid.uuid4(), uuid.uuid4()):
        try:
            await deps.trigger_seller_discovery(run_id, channel_id="C_TEST")
        except AssertionError:
            pass

    # Both distinct run_ids reached the guarded body — the guard keys on
    # run_id, not "has discovery ever run at all".
    assert calls == 2
