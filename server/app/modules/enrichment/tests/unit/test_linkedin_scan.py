import uuid

import pytest

from app.modules.enrichment.application.ports.linkedin import (
    LinkedInUnavailableError,
    PostedLimit,
)
from app.modules.enrichment.application.service import EnrichmentService
from app.modules.enrichment.domain.linkedin import (
    Contact,
    LinkedInPost,
    LinkedInProfile,
    LinkedInTargets,
    ScanOutcome,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.tests.fakes.company_data import FakeCompanyDataClient
from app.modules.enrichment.tests.fakes.extraction import FakeExtractionClient
from app.modules.enrichment.tests.fakes.linkedin import FakeLinkedInClient
from app.modules.enrichment.tests.fakes.linkedin_history import FakeLinkedInHistory
from app.modules.enrichment.tests.fakes.research import FakeResearchClient
from app.modules.enrichment.tests.fakes.role_ports import FakeReviewPort, FakeRoleReader

_JANE_URL = "https://www.linkedin.com/in/jane-doe"
_COMPANY_URL = "https://www.linkedin.com/company/acme-co"


def _contact(pid: str = "p1", url: str | None = _JANE_URL, title: str | None = "CFO") -> Contact:
    return Contact(
        person_attio_id=pid,
        name=f"Person {pid}",
        company_name="Acme Co",
        linkedin_url=url,
        job_title=title,
    )


def _service(
    *,
    targets: LinkedInTargets,
    linkedin_client: FakeLinkedInClient | None,
    linkedin_history: FakeLinkedInHistory | None = None,
) -> EnrichmentService:
    return EnrichmentService(
        research_client=FakeResearchClient(),
        extraction_client=FakeExtractionClient({}),
        role_reader=FakeRoleReader(linkedin_targets=targets),
        review_port=FakeReviewPort(),
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
        linkedin_client=linkedin_client,
        linkedin_history=linkedin_history,
    )


@pytest.fixture
def target() -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),
        org_attio_id="test-org",
        org_name="Acme Co",
    )


# These tests cover the people path (`include_people=True`), kept but not
# wired. Org-only tests are at the end.


async def test_scan_without_a_client_is_empty(target: EnrichmentTarget) -> None:
    service = _service(targets=LinkedInTargets(contacts=(_contact(),)), linkedin_client=None)

    assert (await service.scan_linkedin(target, include_people=True)).is_empty


async def test_scan_detects_job_change_and_returns_posts(target: EnrichmentTarget) -> None:
    post = LinkedInPost(external_id="1", url="https://linkedin.com/posts/1", text="hi")
    client = FakeLinkedInClient(
        profiles=(
            LinkedInProfile(url=f"{_JANE_URL}/", current_title="CFO", current_company="Globex"),
        ),
        posts=(post,),
    )
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(),), company_url=_COMPANY_URL),
        linkedin_client=client,
    )

    scan = await service.scan_linkedin(target, include_people=True)

    assert [c.contact.person_attio_id for c in scan.job_changes] == ["p1"]
    assert scan.job_changes[0].company_changed
    assert scan.posts == (post,)
    # One batched run each; the company page rides along with the posts run.
    assert client.profile_calls == [(_JANE_URL,)]
    assert client.post_calls == [((_JANE_URL, _COMPANY_URL), 10, "month")]


async def test_contact_without_url_is_skipped_and_reported(
    target: EnrichmentTarget, caplog
) -> None:
    client = FakeLinkedInClient(
        profiles=(LinkedInProfile(url=_JANE_URL, current_title="CFO", current_company="Acme Co"),)
    )
    no_url = _contact("p2", url=None)
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(), no_url)), linkedin_client=client
    )

    with caplog.at_level("INFO"):
        scan = await service.scan_linkedin(target, include_people=True)

    assert client.profile_calls == [(_JANE_URL,)]
    assert scan.contacts_without_linkedin == (no_url,)
    # The log identifies the person by id only, never name or URL.
    assert "p2" in caplog.text
    assert "Person p2" not in caplog.text


async def test_no_scrapable_contact_makes_no_vendor_call(target: EnrichmentTarget) -> None:
    client = FakeLinkedInClient()
    no_url = _contact("p2", url=None)
    service = _service(targets=LinkedInTargets(contacts=(no_url,)), linkedin_client=client)

    scan = await service.scan_linkedin(target, include_people=True)

    assert client.profile_calls == [] and client.post_calls == []
    assert scan.contacts_without_linkedin == (no_url,)


async def test_scan_failure_returns_empty_scan_without_raising(target: EnrichmentTarget) -> None:
    client = FakeLinkedInClient(error=RuntimeError("apify down"))
    service = _service(targets=LinkedInTargets(contacts=(_contact(),)), linkedin_client=client)

    assert (await service.scan_linkedin(target, include_people=True)).job_changes == ()


async def test_scan_is_bounded_by_the_overall_timeout(
    target: EnrichmentTarget, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.enrichment.application.linkedin._SCAN_TIMEOUT_S", 0.01)
    client = FakeLinkedInClient(delay_s=1.0)
    service = _service(targets=LinkedInTargets(contacts=(_contact(),)), linkedin_client=client)

    scan = await service.scan_linkedin(target, include_people=True)

    assert scan.job_changes == () and scan.posts == ()


async def test_propose_passes_company_linkedin_url_but_propose_basic_does_not(
    target: EnrichmentTarget,
) -> None:
    from app.modules.enrichment.domain.research_context import CompanyContext

    fake = FakeCompanyDataClient()
    service = EnrichmentService(
        research_client=None,
        extraction_client=FakeExtractionClient({}),
        role_reader=FakeRoleReader(
            context=CompanyContext(org_name="Acme Co", linkedin=_COMPANY_URL)
        ),
        review_port=FakeReviewPort(),
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
        company_data_clients=(fake,),
    )

    await service.propose(target)
    await service.propose_basic(org_name="Acme Co", domain=None, current_values={})

    assert fake.linkedin_urls == [_COMPANY_URL, None]


def _moved_scan_client() -> FakeLinkedInClient:
    post = LinkedInPost(external_id="1", url="https://linkedin.com/posts/1", text="hi")
    return FakeLinkedInClient(
        profiles=(LinkedInProfile(url=_JANE_URL, current_title="CFO", current_company="Globex"),),
        posts=(post,),
    )


async def test_history_makes_a_rerun_report_only_what_is_new(target: EnrichmentTarget) -> None:
    history = FakeLinkedInHistory()
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(),)),
        linkedin_client=_moved_scan_client(),
        linkedin_history=history,
    )

    first = await service.scan_linkedin(target, include_people=True)
    second = await service.scan_linkedin(target, include_people=True)

    assert len(first.posts) == 1 and len(first.job_changes) == 1
    assert second.posts == () and second.job_changes == ()
    assert first.contacts_scanned == 1


async def test_contacts_without_a_url_are_still_reported_on_a_quiet_rerun(
    target: EnrichmentTarget,
) -> None:
    no_url = _contact("p2", url=None)
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(), no_url)),
        linkedin_client=_moved_scan_client(),
        linkedin_history=FakeLinkedInHistory(),
    )

    await service.scan_linkedin(target, include_people=True)
    second = await service.scan_linkedin(target, include_people=True)

    assert second.contacts_without_linkedin == (no_url,)


async def test_a_history_failure_falls_back_to_the_full_scan(
    target: EnrichmentTarget, caplog
) -> None:
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(),)),
        linkedin_client=_moved_scan_client(),
        linkedin_history=FakeLinkedInHistory(error=RuntimeError("db down")),
    )

    with caplog.at_level("WARNING"):
        scan = await service.scan_linkedin(target, include_people=True)

    assert len(scan.posts) == 1 and len(scan.job_changes) == 1
    assert "linkedin_history_failed" in caplog.text


async def test_no_history_is_recorded_when_nothing_was_scrapable(
    target: EnrichmentTarget,
) -> None:
    history = FakeLinkedInHistory()
    service = _service(
        targets=LinkedInTargets(contacts=(_contact(url=None),)),
        linkedin_client=FakeLinkedInClient(),
        linkedin_history=history,
    )

    await service.scan_linkedin(target, include_people=True)

    assert history.calls == 0


# --- org-only scan: the default, and the only mode wired today ---


def _org_service(
    *,
    contacts: tuple[Contact, ...] = (),
    company_url: str | None = _COMPANY_URL,
    client: FakeLinkedInClient | None = None,
    history: FakeLinkedInHistory | None = None,
) -> tuple[EnrichmentService, FakeRoleReader]:
    reader = FakeRoleReader(
        linkedin_targets=LinkedInTargets(contacts=contacts, company_url=company_url)
    )
    service = EnrichmentService(
        research_client=FakeResearchClient(),
        extraction_client=FakeExtractionClient({}),
        role_reader=reader,
        review_port=FakeReviewPort(),
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
        linkedin_client=client or FakeLinkedInClient(),
        linkedin_history=history,
    )
    return service, reader


async def test_org_only_scrapes_just_the_company_page(target: EnrichmentTarget) -> None:
    post = LinkedInPost(external_id="1", url="https://linkedin.com/posts/1", text="hi")
    client = FakeLinkedInClient(posts=(post,))
    service, reader = _org_service(contacts=(_contact(),), client=client)

    scan = await service.scan_linkedin(target)

    assert scan.posts == (post,)
    assert client.profile_calls == []
    assert client.post_calls == [((_COMPANY_URL,), 10, "month")]
    # Contacts are not even read from the database.
    assert reader.include_contacts_calls == [False]
    assert scan.job_changes == () and scan.contacts_without_linkedin == ()
    assert scan.contacts_scanned == 0


async def test_org_only_without_a_company_url_makes_no_vendor_call(
    target: EnrichmentTarget,
) -> None:
    client = FakeLinkedInClient()
    service, _ = _org_service(company_url=None, client=client)

    scan = await service.scan_linkedin(target)

    assert scan.is_empty and scan.outcome is ScanOutcome.SKIPPED
    assert client.profile_calls == [] and client.post_calls == []


async def test_org_only_failure_returns_an_empty_scan(target: EnrichmentTarget) -> None:
    class _Failing(FakeLinkedInClient):
        async def posts(
            self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
        ) -> tuple[LinkedInPost, ...]:
            raise RuntimeError("apify down")

    service, _ = _org_service(client=_Failing())

    scan = await service.scan_linkedin(target)

    assert scan.is_empty and scan.outcome is ScanOutcome.FAILED


async def test_org_only_timeout_returns_an_empty_scan(
    target: EnrichmentTarget, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.enrichment.application.linkedin._SCAN_TIMEOUT_S", 0.01)
    service, _ = _org_service(client=FakeLinkedInClient(delay_s=1.0))

    assert (await service.scan_linkedin(target)).outcome is ScanOutcome.FAILED


async def test_org_only_history_reports_only_new_posts_on_a_rerun(
    target: EnrichmentTarget,
) -> None:
    post = LinkedInPost(external_id="1", url="https://linkedin.com/posts/1", text="hi")
    service, _ = _org_service(
        client=FakeLinkedInClient(posts=(post,)), history=FakeLinkedInHistory()
    )

    first = await service.scan_linkedin(target)
    second = await service.scan_linkedin(target)

    assert first.posts == (post,)
    assert second.is_empty


async def test_the_triggering_user_reaches_the_history(target: EnrichmentTarget) -> None:
    history = FakeLinkedInHistory()
    service, _ = _org_service(history=history)

    await service.scan_linkedin(target, requested_by="U123")

    assert history.requested_by == ["U123"]
    assert history.failures == [None]


async def test_a_failed_scan_is_recorded_with_the_error_type(target: EnrichmentTarget) -> None:
    class _Failing(FakeLinkedInClient):
        async def posts(
            self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
        ) -> tuple[LinkedInPost, ...]:
            raise RuntimeError("apify down: secret detail")

    history = FakeLinkedInHistory()
    service, _ = _org_service(client=_Failing(), history=history)

    scan = await service.scan_linkedin(target, requested_by="U123")

    assert scan.is_empty
    # The type name only: a message can quote data.
    assert history.failures == ["RuntimeError"]
    assert history.requested_by == ["U123"]


async def test_a_timed_out_scan_is_recorded_as_a_timeout(
    target: EnrichmentTarget, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.enrichment.application.linkedin._SCAN_TIMEOUT_S", 0.01)
    history = FakeLinkedInHistory()
    service, _ = _org_service(client=FakeLinkedInClient(delay_s=1.0), history=history)

    await service.scan_linkedin(target)

    assert history.failures == ["TimeoutError"]


async def test_a_history_error_while_recording_a_failure_is_swallowed(
    target: EnrichmentTarget, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.enrichment.application.linkedin._SCAN_TIMEOUT_S", 0.01)
    history = FakeLinkedInHistory(error=RuntimeError("db down"))
    service, _ = _org_service(client=FakeLinkedInClient(delay_s=1.0), history=history)

    scan = await service.scan_linkedin(target)

    assert scan.is_empty and history.calls == 1


async def test_a_skipped_scan_records_nothing(target: EnrichmentTarget) -> None:
    history = FakeLinkedInHistory()
    service, _ = _org_service(company_url=None, history=history)

    await service.scan_linkedin(target, requested_by="U123")

    assert history.calls == 0


async def test_a_scan_without_a_client_is_skipped(target: EnrichmentTarget) -> None:
    service = _service(targets=LinkedInTargets(), linkedin_client=None)

    assert (await service.scan_linkedin(target)).outcome is ScanOutcome.SKIPPED


async def test_a_completed_scan_has_a_completed_outcome(target: EnrichmentTarget) -> None:
    service, _ = _org_service(history=FakeLinkedInHistory())

    scan = await service.scan_linkedin(target)

    # Preserved through the history port, which builds a new scan.
    assert scan.outcome is ScanOutcome.COMPLETED


async def test_a_vendor_failure_is_a_failed_scan_not_an_empty_one(
    target: EnrichmentTarget,
) -> None:
    class _Unavailable(FakeLinkedInClient):
        async def posts(
            self, urls: tuple[str, ...], *, max_posts: int, posted_limit: PostedLimit
        ) -> tuple[LinkedInPost, ...]:
            raise LinkedInUnavailableError("the Apify posts run failed")

    history = FakeLinkedInHistory()
    service, _ = _org_service(client=_Unavailable(), history=history)

    scan = await service.scan_linkedin(target)

    assert scan.outcome is ScanOutcome.FAILED
    assert history.failures == ["LinkedInUnavailableError"]


async def test_a_database_error_loading_targets_is_a_failed_scan(
    target: EnrichmentTarget,
) -> None:
    class _BrokenReader(FakeRoleReader):
        async def load_linkedin_targets(
            self, target: EnrichmentTarget, *, include_contacts: bool = True
        ) -> LinkedInTargets:
            raise RuntimeError("connection lost")

    history = FakeLinkedInHistory()
    service = EnrichmentService(
        research_client=FakeResearchClient(),
        extraction_client=FakeExtractionClient({}),
        role_reader=_BrokenReader(),
        review_port=FakeReviewPort(),
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
        linkedin_client=FakeLinkedInClient(),
        linkedin_history=history,
    )

    scan = await service.scan_linkedin(target, requested_by="U1")

    assert scan.outcome is ScanOutcome.FAILED
    assert history.failures == ["RuntimeError"] and history.requested_by == ["U1"]
