"""Legacy in-channel "Run match anyway" buttons (posted before AZM-133's
popup) still run the match: they reuse their message as the placeholder and
keep the advisor's context. `run_match_and_post` never re-checks discrepancies.
"""

import pytest

from app.modules.discrepancies.domain.criteria import BuyerCriteria
from app.modules.matching_engine.api import dependencies
from app.modules.matching_engine.application.matching.use_cases import MatchRunResult
from app.modules.matching_engine.domain.buyers import BuyerContext


def _buyer(**overrides: object) -> BuyerContext:
    defaults = dict(
        buyer_role_id="buyer-1",
        org_attio_id="org-1",
        org_name="Shahroukh Capital",
        model=None,
        mandate_status=None,
        ebitda_floor=None,
        check_size_min=None,
        check_size_max=None,
        ev_ceiling=None,
        deal_structure_tolerance=None,
        earnout_tolerance=None,
        profitable_only=None,
        investment_strategy=None,
        notes=None,
        contact_person_id=None,
    )
    defaults.update(overrides)
    return BuyerContext(**defaults)  # type: ignore[arg-type]


class _FakeNotifier:
    def __init__(self) -> None:
        self.posted: list[dict] = []
        self.updated: list[dict] = []

    async def post_message(self, **kwargs: object) -> str:
        self.posted.append(kwargs)
        return "100.001"

    async def update_message(self, **kwargs: object) -> None:
        self.updated.append(kwargs)


class _FakeService:
    def __init__(self) -> None:
        self.called = False
        self.advisor_context: str | None = None

    async def run_match(self, buyer, *, requested_by, advisor_context=None):  # noqa: ANN001
        self.called = True
        self.advisor_context = advisor_context
        return MatchRunResult(
            run_id="11111111-1111-1111-1111-111111111111",
            status="GENERATED",
            buyer_org_name=buyer.org_name,
        )


async def _fake_resolve_buyer_by_id(_buyer_role_id: str) -> BuyerContext:
    return _buyer()


async def _noop_async(*_args: object, **_kwargs: object) -> None:
    pass


@pytest.mark.asyncio
async def test_run_match_anyway_reuses_the_report_message_as_the_placeholder(monkeypatch) -> None:
    """The legacy button passes `placeholder_ts` — no second placeholder, no check."""
    notifier = _FakeNotifier()
    service = _FakeService()
    check_calls: list[object] = []

    async def fake_check(criteria: BuyerCriteria, context_text):  # noqa: ANN001
        check_calls.append(criteria)
        raise AssertionError("run_match_and_post must never check discrepancies")

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    await dependencies.run_match_and_post("buyer-1", "U_TEST", "C_TEST", placeholder_ts="200.002")

    assert check_calls == []
    assert notifier.posted == []  # no new placeholder posted
    assert service.called
    assert notifier.updated[-1]["ts"] == "200.002"


@pytest.mark.asyncio
async def test_run_anyway_still_applies_the_advisor_context(monkeypatch) -> None:
    notifier = _FakeNotifier()
    service = _FakeService()
    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)

    await dependencies.run_match_and_post(
        "buyer-1",
        "U_TEST",
        "C_TEST",
        advisor_context="I want Egypt",
        placeholder_ts="100.001",
    )

    assert service.called
    assert service.advisor_context == "I want Egypt"
