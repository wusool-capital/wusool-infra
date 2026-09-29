"""The discrepancy check ahead of `/find-match` (§ AZM-92/WP3): a conflict
pauses the match behind "Run match anyway"/"Cancel" buttons; a missing-only
result posts a note and the match still runs; a check failure never blocks
matching at all.
"""

import pytest

from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.domain.criteria import BuyerCriteria, Discrepancy, DiscrepancyReport
from app.modules.discrepancies.domain.vocabulary import Criterion
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

    async def run_match(self, buyer, *, requested_by):  # noqa: ANN001
        self.called = True
        return MatchRunResult(
            run_id="11111111-1111-1111-1111-111111111111",
            status="GENERATED",
            buyer_org_name=buyer.org_name,
        )


def _report(*, conflicts=(), missing=()) -> DiscrepancyReport:
    return DiscrepancyReport(buyer_role_id="buyer-1", conflicts=conflicts, missing=missing)


async def _fake_resolve_buyer_by_id(_buyer_role_id: str) -> BuyerContext:
    return _buyer()


async def _noop_async(*_args: object, **_kwargs: object) -> None:
    pass


@pytest.mark.asyncio
async def test_conflict_pauses_the_match_behind_buttons(monkeypatch) -> None:
    notifier = _FakeNotifier()
    service = _FakeService()
    conflict = Discrepancy(Criterion.VERTICAL, "conflict", stored="Pharma", stated="Garage")
    result = DiscrepancyCheckResult(report=_report(conflicts=(conflict,)), message="Heads up.")

    async def fake_check(criteria: BuyerCriteria, context_text):  # noqa: ANN001
        return result

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    await dependencies.run_match_and_post(
        "buyer-1", "U_TEST", "C_TEST", advisor_context="Garage only", check_discrepancies=True
    )

    assert not service.called
    assert len(notifier.updated) == 1
    assert notifier.updated[0]["text"] == "Heads up."


@pytest.mark.asyncio
async def test_missing_only_posts_a_note_and_still_matches(monkeypatch) -> None:
    notifier = _FakeNotifier()
    service = _FakeService()
    missing = Discrepancy(Criterion.EBITDA, "missing", stored="(not set)")
    result = DiscrepancyCheckResult(report=_report(missing=(missing,)), message="Missing EBITDA.")

    async def fake_check(criteria: BuyerCriteria, context_text):  # noqa: ANN001
        return result

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    await dependencies.run_match_and_post(
        "buyer-1", "U_TEST", "C_TEST", check_discrepancies=True
    )

    assert service.called
    assert any(p["text"] == "Missing EBITDA." for p in notifier.posted)


@pytest.mark.asyncio
async def test_discrepancy_check_failure_never_blocks_matching(monkeypatch) -> None:
    notifier = _FakeNotifier()
    service = _FakeService()

    async def fake_check(criteria: BuyerCriteria, context_text):  # noqa: ANN001
        raise RuntimeError("adapter exploded")

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    await dependencies.run_match_and_post(
        "buyer-1", "U_TEST", "C_TEST", check_discrepancies=True
    )

    assert service.called


@pytest.mark.asyncio
async def test_clear_report_runs_the_match_silently(monkeypatch) -> None:
    notifier = _FakeNotifier()
    service = _FakeService()
    result = DiscrepancyCheckResult(
        report=_report(), message="No conflicts or missing criteria found."
    )

    async def fake_check(criteria: BuyerCriteria, context_text):  # noqa: ANN001
        return result

    monkeypatch.setattr(dependencies, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", _fake_resolve_buyer_by_id)
    monkeypatch.setattr(
        "app.modules.matching_engine.api.dependencies.matching_engine_service",
        lambda _session: service,
    )
    monkeypatch.setattr(dependencies, "trigger_seller_discovery", _noop_async)
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    await dependencies.run_match_and_post(
        "buyer-1", "U_TEST", "C_TEST", check_discrepancies=True
    )

    assert service.called
    # Only the initial "Finding matches…" placeholder — no discrepancy note.
    assert len(notifier.posted) == 1


@pytest.mark.asyncio
async def test_run_match_anyway_reuses_the_report_message_as_the_placeholder(monkeypatch) -> None:
    """The "Run match anyway" button passes `placeholder_ts` and
    `check_discrepancies=False` — no second placeholder, no second check."""
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
        "buyer-1", "U_TEST", "C_TEST", placeholder_ts="200.002"
    )

    assert notifier.posted == []  # no new placeholder posted
    assert service.called
    assert notifier.updated[-1]["ts"] == "200.002"
