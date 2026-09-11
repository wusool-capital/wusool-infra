"""Coverage for `_enrich_and_notify` — the glue the per-candidate "Enrich"
button on a match result calls into. It has no logic of its own beyond
delegating to `enrichment.enrich_and_post` with the right
kind/role_id/channel — `enrichment` owns everything past that (org
resolution, research, the review hand-off). Kept kind-agnostic (tested for
both "seller" and "buyer") even though only the seller match-result button
calls it today.
"""

from app.modules.matching_engine.api.slack.handlers.actions import _enrich_and_notify


async def test_enrich_and_notify_delegates_to_enrichment(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    async def fake_enrich_and_post(*, kind: str, role_id: str, channel_id: str) -> None:
        calls.append((kind, role_id, channel_id))

    monkeypatch.setattr("app.modules.enrichment.enrich_and_post", fake_enrich_and_post)

    await _enrich_and_notify(kind="seller", role_id="role-1", channel_id="C_TEST")

    assert calls == [("seller", "role-1", "C_TEST")]


async def test_enrich_and_notify_works_for_buyer_kind_too(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    async def fake_enrich_and_post(*, kind: str, role_id: str, channel_id: str) -> None:
        calls.append((kind, role_id, channel_id))

    monkeypatch.setattr("app.modules.enrichment.enrich_and_post", fake_enrich_and_post)

    await _enrich_and_notify(kind="buyer", role_id="buyer-1", channel_id="C_TEST")

    assert calls == [("buyer", "buyer-1", "C_TEST")]
