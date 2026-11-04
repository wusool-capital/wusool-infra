"""Full research on an approved discovered seller: the job that fills it in,
and the save that writes the chosen fields once."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.enrichment import (
    EnrichmentProposal,
    LinkedInPost,
    LinkedInScan,
    ProposedFieldValue,
    WriteTarget,
)
from app.modules.matching_engine.api.http import web_research
from app.modules.matching_engine.application.ports.seller_edits import (
    SellerEditOutcome,
    SellerEditResult,
)
from app.modules.matching_engine.application.research import (
    ResearchMixin,
    ResearchNotReadyError,
    ResearchSaveInProgressError,
)
from app.modules.matching_engine.domain.matching.research import (
    ResearchField,
    ResearchLinkedIn,
    ResearchRecord,
)

_ROLE = str(uuid.uuid4())
_ID = uuid.uuid4()


class _Store:
    """One candidate row's research, with the repository's claim rules."""

    def __init__(self, record: ResearchRecord | None = None) -> None:
        self.record = record
        self.save_claimed = False
        self.writes: list[ResearchRecord] = []

    async def get_by_id(self, _id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(research=self.record, seller_role_id=_ROLE)

    async def update_research(self, _id: uuid.UUID, record: ResearchRecord) -> None:
        self.record = record
        self.save_claimed = False
        self.writes.append(record)

    async def claim_research_save(self, _id: uuid.UUID, **_kw: datetime) -> bool:
        if self.save_claimed:
            return False
        self.save_claimed = True
        return True


def _service(store: _Store) -> ResearchMixin:
    service = ResearchMixin.__new__(ResearchMixin)

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(match_results=store)

    service._uow_factory = uow
    return service


def _field(name: str) -> ResearchField:
    return ResearchField(name, "seller_role", ["Security"], "Security", 0.9, "https://s", "why")


def _done(*names: str, saved: tuple[str, ...] = ()) -> ResearchRecord:
    return ResearchRecord(
        claimed_at=datetime.now(UTC),
        outcome="done",
        fields=tuple(_field(n) for n in names),
        saved_fields=saved,
    )


async def _save(service: ResearchMixin, editor: AsyncMock, *names: str) -> SellerEditResult:
    return await service.save_research(
        _ID,
        field_names=names,
        requested_by="U1",
        editor=SimpleNamespace(apply=editor),
        stale_after=timedelta(minutes=15),
    )


async def test_save_writes_only_unsaved_chosen_fields_and_records_them() -> None:
    store = _Store(_done("sector_focus", "region", "facebook", saved=("region",)))
    editor = AsyncMock(return_value=SellerEditResult(outcome=SellerEditOutcome.SAVED))

    result = await _save(_service(store), editor, "sector_focus", "region")

    assert result.outcome is SellerEditOutcome.SAVED
    edits = editor.await_args.kwargs["edits"]
    assert [e.name for e in edits] == ["sector_focus"]
    assert editor.await_args.kwargs["requested_by"] == "U1"
    assert store.record is not None
    assert store.record.saved_fields == ("region", "sector_focus")
    assert store.record.saving_at is None


async def test_a_failed_save_records_nothing_and_releases_the_claim() -> None:
    store = _Store(_done("sector_focus"))
    editor = AsyncMock(
        return_value=SellerEditResult(outcome=SellerEditOutcome.CONFLICT, conflicts=("x",))
    )

    result = await _save(_service(store), editor, "sector_focus")

    assert result.outcome is SellerEditOutcome.CONFLICT
    assert store.record is not None and store.record.saved_fields == ()
    assert store.save_claimed is False


async def test_a_second_save_while_one_runs_is_refused() -> None:
    store = _Store(_done("sector_focus"))
    store.save_claimed = True

    with pytest.raises(ResearchSaveInProgressError):
        await _save(_service(store), AsyncMock(), "sector_focus")


async def test_saving_unfinished_research_is_refused() -> None:
    store = _Store(ResearchRecord(claimed_at=datetime.now(UTC)))

    with pytest.raises(ResearchNotReadyError):
        await _save(_service(store), AsyncMock(), "sector_focus")


async def test_saving_already_saved_fields_writes_nothing() -> None:
    store = _Store(_done("sector_focus", saved=("sector_focus",)))
    editor = AsyncMock()

    result = await _save(_service(store), editor, "sector_focus")

    assert result.outcome is SellerEditOutcome.SAVED
    editor.assert_not_awaited()


# The job ---------------------------------------------------------------------


@pytest.fixture
def job(monkeypatch):
    store = _Store(ResearchRecord(claimed_at=datetime.now(UTC)))

    @asynccontextmanager
    async def _open():
        yield _service(store)

    monkeypatch.setattr(web_research, "open_matching_engine_service", _open)
    return store


def _proposal() -> EnrichmentProposal:
    return EnrichmentProposal(
        target=SimpleNamespace(),
        values=(
            ProposedFieldValue(
                field_name="sector_focus",
                write_target=WriteTarget.SELLER_ROLE,
                current=None,
                proposed=["Security Services"],
                source_url="https://sun.example",
                confidence=0.9,
                rationale="Their site says so.",
            ),
        ),
        generated_by_model="m",
    )


def _scan() -> LinkedInScan:
    return LinkedInScan(posts=(LinkedInPost(external_id="p1", url="https://li/p1", text="Hi"),))


async def test_research_keeps_the_proposal_and_the_linkedin_scan(job, monkeypatch) -> None:
    monkeypatch.setattr(web_research, "propose_for_role", AsyncMock(return_value=_proposal()))
    monkeypatch.setattr(web_research, "scan_linkedin_for_role", AsyncMock(return_value=_scan()))

    await web_research.research_seller(_ID, seller_role_id=_ROLE, requested_by="U1")

    record = job.record
    assert record.outcome == "done"
    assert [(f.name, f.target, f.display) for f in record.fields] == [
        ("sector_focus", "seller_role", "Security Services")
    ]
    assert record.linkedin is not None
    assert [p.url for p in record.linkedin.posts] == ["https://li/p1"]
    # Stored once on its own before the finished record, so a crash keeps it.
    assert job.writes[0].outcome is None and job.writes[0].linkedin is not None


async def test_a_retry_reuses_the_stored_scan(job, monkeypatch) -> None:
    kept = ResearchLinkedIn(outcome="completed")
    job.record = ResearchRecord(claimed_at=datetime.now(UTC), linkedin=kept)
    scan = AsyncMock()
    monkeypatch.setattr(web_research, "propose_for_role", AsyncMock(return_value=_proposal()))
    monkeypatch.setattr(web_research, "scan_linkedin_for_role", scan)

    await web_research.research_seller(_ID, seller_role_id=_ROLE, requested_by="U1")

    scan.assert_not_awaited()
    assert job.record.linkedin == kept


async def test_a_failed_proposal_is_recorded_with_the_scan(job, monkeypatch) -> None:
    monkeypatch.setattr(web_research, "propose_for_role", AsyncMock(side_effect=RuntimeError))
    monkeypatch.setattr(web_research, "scan_linkedin_for_role", AsyncMock(return_value=_scan()))

    await web_research.research_seller(_ID, seller_role_id=_ROLE, requested_by="U1")

    assert job.record.outcome == "failed"
    assert job.record.error == "Research didn't finish."
    assert job.record.linkedin is not None


async def test_a_failed_scan_still_finishes_the_research(job, monkeypatch) -> None:
    monkeypatch.setattr(web_research, "propose_for_role", AsyncMock(return_value=_proposal()))
    monkeypatch.setattr(web_research, "scan_linkedin_for_role", AsyncMock(side_effect=RuntimeError))

    await web_research.research_seller(_ID, seller_role_id=_ROLE, requested_by="U1")

    assert job.record.outcome == "done"
    assert job.record.linkedin == ResearchLinkedIn(outcome="failed")
