import pytest

from app.modules.matching.application.use_cases import MatchRunResult
from app.modules.slack import match_dispatch


@pytest.mark.asyncio
async def test_unexpected_background_failure_replaces_placeholder(monkeypatch) -> None:
    updates: list[dict] = []

    class FakeClient:
        async def chat_postMessage(self, **kwargs):  # noqa: ANN001
            return {"ts": "123.456"}

        async def chat_update(self, **kwargs):  # noqa: ANN001
            updates.append(kwargs)

    class FakeApp:
        client = FakeClient()

    class FakeRunUseCase:
        async def execute(self, buyer, *, requested_by):  # noqa: ANN001
            return MatchRunResult(
                run_id="run-1", status="GENERATED", buyer_org_name=buyer.org_name
            )

    class Buyer:
        org_name = "Acme Capital"

    async def fake_buyer_lookup(_buyer_role_id):
        return Buyer()

    monkeypatch.setattr("app.modules.slack.bolt_app.get_bolt_app", lambda: FakeApp())
    monkeypatch.setattr(match_dispatch, "resolve_buyer_by_id", fake_buyer_lookup)
    monkeypatch.setattr(match_dispatch, "build_run_match_use_case", lambda: FakeRunUseCase())
    monkeypatch.setattr(
        match_dispatch,
        "build_match_result_blocks",
        lambda _result: (_ for _ in ()).throw(RuntimeError("render exploded")),
    )

    await match_dispatch.run_match_and_post("buyer-1", "U_TEST", "C_TEST")

    assert updates[-1] == {
        "channel": "C_TEST",
        "ts": "123.456",
        "text": "Matching failed unexpectedly. Please try again.",
    }
