import pytest

from app.modules.matching_engine.api import dependencies
from app.modules.matching_engine.application.matching.use_cases import MatchRunResult


@pytest.mark.asyncio
async def test_unexpected_background_failure_replaces_placeholder(monkeypatch) -> None:
    updates: list[dict] = []

    class FakeNotifier:
        async def post_message(self, **kwargs):  # noqa: ANN001
            return "123.456"

        async def update_message(self, **kwargs):  # noqa: ANN001
            updates.append(kwargs)

    class FakeRunUseCase:
        async def execute(self, buyer, *, requested_by):  # noqa: ANN001
            return MatchRunResult(
                run_id="run-1", status="GENERATED", buyer_org_name=buyer.org_name
            )

    class Buyer:
        org_name = "Acme Capital"

    async def fake_buyer_lookup(_buyer_role_id):
        return Buyer()

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", fake_buyer_lookup)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.build_run_match_use_case",
        lambda: FakeRunUseCase(),
    )
    monkeypatch.setattr(
        "app.modules.matching_engine.api.slack.views.match_result.build_match_result_blocks",
        lambda _result: (_ for _ in ()).throw(RuntimeError("render exploded")),
    )

    await dependencies.run_match_and_post("buyer-1", "U_TEST", "C_TEST")

    assert updates[-1] == {
        "channel": "C_TEST",
        "ts": "123.456",
        "text": "Matching failed unexpectedly. Please try again.",
    }
