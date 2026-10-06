"""Discovered sellers as review candidates: appended after the CRM shortlist,
rendered as their own message, and posted by `trigger_seller_discovery`."""

import uuid
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.modules.discovery as discovery_module
from app.modules.discovery import (
    CreatedSeller,
    DiscoveredLead,
    DiscoveryOutcome,
    FailedLead,
    PossibleDuplicate,
    SellerDraft,
    UnverifiedSeller,
)
from app.modules.matching_engine.api import dependencies as deps
from app.modules.matching_engine.api.slack.views.discovered_candidates import (
    build_discovered_candidates_blocks,
)
from app.modules.matching_engine.application.approvals import MatchNotFoundError
from app.modules.matching_engine.application.matching.use_cases import (
    MatchingMixin,
    MatchResultView,
    MatchRunView,
)
from app.modules.matching_engine.domain.matching.entities import DiscoveredCandidate
from app.modules.matching_engine.persistence import mappers
from app.modules.matching_engine.persistence.mappers import to_match_result_entity


class _UoW:
    def __init__(self, uow: SimpleNamespace) -> None:
        self._uow = uow

    async def __aenter__(self) -> SimpleNamespace:
        return self._uow

    async def __aexit__(self, *_args: object) -> bool:
        return False


def _service(*, run: SimpleNamespace | None, existing: list[SimpleNamespace]):
    repo = SimpleNamespace(
        get_run=AsyncMock(return_value=run),
        get_candidates=AsyncMock(return_value=existing),
        create_candidates=AsyncMock(),
    )
    uow = SimpleNamespace(match_results=repo)
    service = MatchingMixin(
        lambda: _UoW(uow),
        buyer_repository=SimpleNamespace(),
        extraction_service=SimpleNamespace(),
        reasoning_service=SimpleNamespace(),
        candidate_retriever=SimpleNamespace(),
        scoring_engine=SimpleNamespace(),
        top_n=0,
        deal_gateway=SimpleNamespace(),
    )
    return service, repo


def _candidate(name: str) -> DiscoveredCandidate:
    return DiscoveredCandidate(
        seller_role_id=str(uuid.uuid4()), seller_attio_id=f"attio-{name}", source_url="https://m/x"
    )


async def test_append_ranks_after_the_existing_shortlist_and_marks_origin() -> None:
    run = SimpleNamespace(buyer_attio_id="buyer-1", buyer_role_id=str(uuid.uuid4()))
    service, repo = _service(run=run, existing=[SimpleNamespace(rank=1), SimpleNamespace(rank=3)])

    await service.append_discovered_candidates(uuid.uuid4(), [_candidate("a"), _candidate("b")])

    rows = repo.create_candidates.await_args.args[0]
    assert [r["rank"] for r in rows] == [4, 5]
    assert {r["status"] for r in rows} == {"PENDING_REVIEW"}
    assert rows[0]["metadata_"] == {"origin": "discovery", "source_url": "https://m/x"}
    assert rows[0]["buyer_attio_id"] == "buyer-1"
    assert "match_score" not in rows[0]


async def test_append_with_no_candidates_touches_nothing() -> None:
    service, repo = _service(run=None, existing=[])

    await service.append_discovered_candidates(uuid.uuid4(), [])

    repo.get_run.assert_not_awaited()


async def test_append_for_an_unknown_run_raises() -> None:
    service, _ = _service(run=None, existing=[])

    with pytest.raises(MatchNotFoundError):
        await service.append_discovered_candidates(uuid.uuid4(), [_candidate("a")])


def _view(status: str = "PENDING_REVIEW", decision: str | None = None) -> MatchResultView:
    return MatchResultView(
        match_result_id="m1",
        rank=4,
        seller_role_id="s1",
        seller_org_name="Acme Co",
        match_score=0.0,
        data_confidence=0.0,
        why_it_matches=None,
        status=status,
        approved_by="U1" if decision else None,
        decision=decision,
        origin="discovery",
        source_url="https://maps.example/acme",
    )


def test_pending_discovered_candidate_gets_approve_and_reject_only() -> None:
    blocks = build_discovered_candidates_blocks([_view()], notes=["2 more already in the CRM."])
    dicts = [b.to_dict() for b in blocks]

    actions = next(d for d in dicts if d["type"] == "actions")
    assert [e["action_id"] for e in actions["elements"]] == ["approve_match", "reject_match"]
    assert {e["value"] for e in actions["elements"]} == {"m1"}
    assert "View on Maps" in next(d for d in dicts if d["type"] == "section")["text"]["text"]
    assert "2 more already in the CRM." in dicts[-1]["elements"][0]["text"]


def test_discovered_sellers_are_numbered_from_one_not_by_stored_rank() -> None:
    """AZM-133: stored ranks continue after the CRM shortlist (4, 5, ...)."""
    rows = [replace(_view(), rank=rank, seller_org_name=f"Co {rank}") for rank in (4, 5, 6)]
    sections = [
        b.to_dict()["text"]["text"]
        for b in build_discovered_candidates_blocks(rows)
        if b.to_dict()["type"] == "section"
    ]

    assert [s.split(".")[0] for s in sections] == ["*1", "*2", "*3"]


def test_decided_discovered_candidate_shows_the_decision_not_buttons() -> None:
    dicts = [
        b.to_dict() for b in build_discovered_candidates_blocks([_view("APPROVED", "APPROVED")])
    ]

    assert not any(d["type"] == "actions" for d in dicts)
    assert "APPROVED" in dicts[-1]["elements"][0]["text"]


def test_mapper_reads_origin_and_source_url_from_metadata() -> None:
    def _row(metadata: dict) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(), run_id=uuid.uuid4(), rank=1, status="PENDING_REVIEW",
            buyer_attio_id="b", buyer_role_id=uuid.uuid4(), seller_attio_id="s",
            seller_role_id=None, match_score_id=None, match_score=None, data_confidence=None,
            why_chosen_over_alternatives=None, recommended_pitch=None, risks_and_gaps=None,
            approved_by=None, decision=None, decision_notes=None, decided_at=None,
            deal_attio_id=None, requested_by=None, model_version=None,
            requirement_profile_version=None, requirement_profile=None,
            candidates_considered=None, candidates_filtered=None, filters_skipped=[],
            final_candidate_ids=None, execution_duration_ms=None, errors=None,
            started_at=None, completed_at=None, metadata_=metadata,
        )  # fmt: skip

    discovered = _entity(_row({"origin": "discovery", "source_url": "https://m/x"}))
    plain = _entity(_row({}))

    assert (discovered.origin, discovered.source_url) == ("discovery", "https://m/x")
    assert (plain.origin, plain.source_url) == ("crm", None)


def _entity(row: SimpleNamespace):
    # A bare namespace has no ORM state for `_loaded_org_name` to inspect.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mappers, "_loaded_org_name", lambda *_a, **_k: None)
    try:
        return to_match_result_entity(row)  # ty: ignore[invalid-argument-type]
    finally:
        monkeypatch.undo()


class _Notifier:
    def __init__(self) -> None:
        self.updates: list[dict] = []
        self.posts: list[dict] = []

    async def post_message(self, **kwargs: object) -> str:
        self.posts.append(kwargs)
        return "ts-1"

    async def update_message(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch):
    seller_role_id = uuid.uuid4()
    service = SimpleNamespace(
        get_match_analysis=AsyncMock(
            return_value=SimpleNamespace(
                run=SimpleNamespace(requirement_profile=object(), buyer_role_id="buyer-role-1")
            )
        ),
        append_discovered_candidates=AsyncMock(),
        get_match_run_view=AsyncMock(
            return_value=MatchRunView(
                run_id="r1",
                buyer_org_name="Buyer Co",
                results=[replace(_view(), seller_role_id=str(seller_role_id))],
            )
        ),
    )
    notifier = _Notifier()
    monkeypatch.setattr(deps, "matching_engine_service", lambda _session: service)
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: _UoW(SimpleNamespace()))
    monkeypatch.setattr(deps, "_build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(
        "app.modules.matching_engine.application.discovery_bridge.extract_query_terms",
        lambda _profile: ("Retail", "UAE", ()),
    )
    return SimpleNamespace(service=service, notifier=notifier, seller_role_id=seller_role_id)


async def test_trigger_appends_created_sellers_and_posts_duplicates_separately(
    monkeypatch, harness
) -> None:
    lead = DiscoveredLead(name="Twin Co", source_url="https://m/t")
    outcome = DiscoveryOutcome(
        status="ok",
        created=(
            CreatedSeller(
                seller_role_id=harness.seller_role_id,
                org_attio_id="attio-acme",
                org_name="Acme Co",
                source_url="https://maps.example/acme",
            ),
        ),
        possible_duplicates=(PossibleDuplicate(lead=lead, existing_org_name="Twin Holdings"),),
        failed=(FailedLead(lead=DiscoveredLead(name="Bad Co", source_url="u"), reason="x"),),
        already_in_crm=2,
    )
    discover = AsyncMock(return_value=outcome)
    monkeypatch.setattr(discovery_module, "discover_and_create_sellers", discover)

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    assert discover.await_args.kwargs["quota_key"] == "buyer-role-1"
    appended = harness.service.append_discovered_candidates.await_args.args[1]
    assert [c.seller_attio_id for c in appended] == ["attio-acme"]
    final = harness.notifier.updates[-1]
    assert final["text"] == "Found 1 new seller(s)"
    rendered = str([b.to_dict() for b in final["blocks"]])
    assert "2 more already in the CRM." in rendered
    assert "Couldn't save: Bad Co." in rendered
    assert len(harness.notifier.posts) == 2  # the placeholder, then the duplicates message
    assert "possible duplicate" in harness.notifier.posts[1]["text"]


async def test_trigger_posts_a_review_message_per_unverified_lead(monkeypatch, harness) -> None:
    unverified = UnverifiedSeller(
        draft=SellerDraft(org_name="Acme Co", source_urls=("https://maps.example/acme",)),
        maps_website="acme.com",
        provider_websites=(("Diffbot", "acme-group.de"),),
        values=(),
        review_id="p1",
    )
    marked = AsyncMock()
    monkeypatch.setattr(discovery_module, "mark_review_posted", marked)
    monkeypatch.setattr(
        discovery_module,
        "discover_and_create_sellers",
        AsyncMock(return_value=DiscoveryOutcome(status="ok", needs_review=(unverified,))),
    )

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    assert harness.notifier.updates[-1]["text"] == (
        "No new sellers created. 1 needs a website review before saving (below)."
    )
    review = harness.notifier.posts[1]
    assert review["text"] == "Website check for Acme Co"
    marked.assert_awaited_once_with("p1")
    assert review["blocks"][-1].to_dict()["accessory"]["text"]["text"] == "Review & Save"


async def test_trigger_notes_leads_still_awaiting_an_earlier_review(monkeypatch, harness) -> None:
    monkeypatch.setattr(
        discovery_module,
        "discover_and_create_sellers",
        AsyncMock(return_value=DiscoveryOutcome(status="ok", awaiting_review=2)),
    )

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    assert "2 still awaiting an earlier website review." in harness.notifier.updates[-1]["text"]


async def test_one_failed_review_post_does_not_stop_the_others(monkeypatch, harness) -> None:
    def _unverified(name: str) -> UnverifiedSeller:
        return UnverifiedSeller(
            draft=SellerDraft(org_name=name),
            maps_website=None,
            provider_websites=(),
            values=(),
            review_id=name,
        )

    marked = AsyncMock()
    monkeypatch.setattr(discovery_module, "mark_review_posted", marked)

    monkeypatch.setattr(
        discovery_module,
        "discover_and_create_sellers",
        AsyncMock(
            return_value=DiscoveryOutcome(
                status="ok", needs_review=(_unverified("Bad Co"), _unverified("Good Co"))
            )
        ),
    )
    original = harness.notifier.post_message

    async def _flaky(**kwargs: object) -> str:
        if kwargs["text"] == "Website check for Bad Co":
            raise RuntimeError("invalid_blocks")
        return await original(**kwargs)

    harness.notifier.post_message = _flaky

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    assert [p["text"] for p in harness.notifier.posts][-1] == "Website check for Good Co"
    marked.assert_awaited_once_with("Good Co")  # the failed card stays unmarked


async def test_trigger_reports_the_daily_cap_and_creates_nothing(monkeypatch, harness) -> None:
    monkeypatch.setattr(
        discovery_module,
        "discover_and_create_sellers",
        AsyncMock(return_value=DiscoveryOutcome(status="daily_cap_reached")),
    )

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    assert "Daily discovery limit" in harness.notifier.updates[-1]["text"]
    harness.service.append_discovered_candidates.assert_not_awaited()


class _RecordingRunner:
    def __init__(self) -> None:
        self.names: list[str] = []

    def run(self, coro_factory, *, name: str) -> None:
        self.names.append(name)


def _decision_harness(monkeypatch: pytest.MonkeyPatch, *, origin: str):
    from app.modules.matching_engine.api.slack.handlers import actions

    row = replace(_view("APPROVED", "APPROVED"), origin=origin)  # ty: ignore[invalid-argument-type]

    def _result(status: str) -> SimpleNamespace:
        return SimpleNamespace(
            match_result_id="m1", run_id=str(uuid.uuid4()), seller_org_name="Acme", status=status
        )

    service = SimpleNamespace(
        approve_match=AsyncMock(return_value=_result("APPROVED")),
        reject_match=AsyncMock(return_value=_result("REJECTED")),
        get_match_run_view=AsyncMock(
            return_value=MatchRunView(run_id="r1", buyer_org_name="Buyer", results=[row])
        ),
    )  # fmt: skip
    runner = _RecordingRunner()
    monkeypatch.setattr(actions, "matching_engine_service", lambda _s: service)
    monkeypatch.setattr(actions, "get_sessionmaker", lambda: lambda: _UoW(SimpleNamespace()))
    monkeypatch.setattr(actions, "_task_runner", runner)
    client = SimpleNamespace(chat_postEphemeral=AsyncMock())
    body = {
        "channel": {"id": "C1"},
        "user": {"id": "U1"},
        "actions": [{"value": str(uuid.uuid4())}],
    }
    return actions, client, AsyncMock(), body, runner


@pytest.mark.parametrize(
    ("origin", "decision", "expected"),
    [
        ("discovery", "approve", ["enrich-approved:s1"]),
        ("discovery", "reject", []),
        ("crm", "approve", []),
    ],
)
async def test_only_approving_a_discovered_seller_triggers_full_enrichment(
    monkeypatch, origin, decision, expected
) -> None:
    actions, client, respond, body, runner = _decision_harness(monkeypatch, origin=origin)

    await actions._handle_decision(body, client, respond, decision)

    assert runner.names == expected


async def test_review_setup_failure_says_the_sellers_were_created(monkeypatch, harness) -> None:
    outcome = DiscoveryOutcome(
        status="ok",
        created=(
            CreatedSeller(
                seller_role_id=harness.seller_role_id,
                org_attio_id="attio-acme",
                org_name="Acme Co",
                source_url="https://maps.example/acme",
            ),
        ),
    )
    monkeypatch.setattr(
        discovery_module, "discover_and_create_sellers", AsyncMock(return_value=outcome)
    )
    harness.service.append_discovered_candidates.side_effect = RuntimeError("db down")

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    text = harness.notifier.updates[-1]["text"]
    assert "Created 1 seller(s) in the CRM (Acme Co)" in text
    assert "failed unexpectedly" not in text


async def test_a_partly_saved_lead_says_what_landed(monkeypatch, harness) -> None:
    failed = FailedLead(
        lead=DiscoveredLead(name="Half Co", source_url="u"),
        reason="db",
        landed=("organization created in Attio",),
    )
    outcome = DiscoveryOutcome(
        status="ok",
        created=(
            CreatedSeller(
                seller_role_id=harness.seller_role_id,
                org_attio_id="attio-acme",
                org_name="Acme Co",
                source_url="https://maps.example/acme",
            ),
        ),
        failed=(failed,),
    )
    monkeypatch.setattr(
        discovery_module, "discover_and_create_sellers", AsyncMock(return_value=outcome)
    )

    await deps.trigger_seller_discovery(uuid.uuid4(), channel_id="C1")

    rendered = str([b.to_dict() for b in harness.notifier.updates[-1]["blocks"]])
    assert "Half Co (partly saved: organization created in Attio)" in rendered
