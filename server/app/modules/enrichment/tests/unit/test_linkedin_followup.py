"""The LinkedIn thread reply must never cost the proposal: it is posted
after the proposal update, in the placeholder's thread, and its own
failures are swallowed.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from slack_sdk.models.blocks import Block, SectionBlock

from app.modules.enrichment.api import dependencies
from app.modules.enrichment.domain.linkedin import LinkedInPost, LinkedInScan, ScanOutcome
from app.modules.enrichment.domain.proposals import EnrichmentProposal
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.tests.fakes.linkedin import FakeLinkedInClient


@dataclass(frozen=True)
class _Message:
    channel: str
    text: str
    thread_ts: str | None = None
    body: str = ""


@dataclass(frozen=True)
class _Update:
    channel: str
    ts: str
    text: str


class _Notifier:
    def __init__(self) -> None:
        self.posts: list[_Message] = []
        self.updates: list[_Update] = []

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        blocks: Sequence[Block] | None = None,
        thread_ts: str | None = None,
    ) -> str:
        body = "\n".join(b.text.text for b in blocks or () if isinstance(b, SectionBlock))
        self.posts.append(_Message(channel=channel, text=text, thread_ts=thread_ts, body=body))
        return "ts-reply" if thread_ts else "ts-placeholder"

    async def update_message(
        self, *, channel: str, ts: str, text: str, blocks: Sequence[Block] | None = None
    ) -> None:
        self.updates.append(_Update(channel=channel, ts=ts, text=text))


class _Service:
    def __init__(self, scan: LinkedInScan | Exception, propose_error: bool = False) -> None:
        self._scan = scan
        self._propose_error = propose_error
        self.scans = 0
        self.requested_by: list[str | None] = []

    async def propose(self, target: EnrichmentTarget) -> EnrichmentProposal:
        if self._propose_error:
            raise RuntimeError("boom")
        return EnrichmentProposal(target=target, values=(), generated_by_model="m")

    async def scan_linkedin(
        self, target: EnrichmentTarget, *, requested_by: str | None = None
    ) -> LinkedInScan:
        self.scans += 1
        self.requested_by.append(requested_by)
        if isinstance(self._scan, Exception):
            raise self._scan
        return self._scan


@pytest.fixture
def target() -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),
        org_attio_id="test-org",
        org_name="Acme Co",
    )


def _wire(monkeypatch, service: _Service, *, linkedin_configured: bool = True) -> _Notifier:
    notifier = _Notifier()
    monkeypatch.setattr(dependencies, "slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "enrichment_service", lambda: service)
    monkeypatch.setattr(
        dependencies,
        "_linkedin_client",
        lambda: FakeLinkedInClient() if linkedin_configured else None,
    )
    return notifier


async def test_follow_up_is_a_reply_in_the_placeholders_thread(
    monkeypatch, target: EnrichmentTarget
) -> None:
    scan = LinkedInScan(
        posts=(LinkedInPost(external_id="1", url="https://linkedin.com/posts/1", text="hi"),)
    )
    notifier = _wire(monkeypatch, _Service(scan))

    await dependencies.propose_and_post(target, channel_id="C1")

    assert len(notifier.updates) == 1  # the proposal itself
    assert notifier.posts[1].thread_ts == "ts-placeholder"
    assert notifier.posts[1].channel == "C1"


async def test_a_scan_with_nothing_new_says_so(monkeypatch, target: EnrichmentTarget) -> None:
    notifier = _wire(monkeypatch, _Service(LinkedInScan()))

    await dependencies.propose_and_post(target, channel_id="C1")

    assert len(notifier.posts) == 2
    assert "No new posts" in notifier.posts[1].body


async def test_a_skipped_scan_says_no_linkedin_page_is_saved(
    monkeypatch, target: EnrichmentTarget
) -> None:
    notifier = _wire(monkeypatch, _Service(LinkedInScan(outcome=ScanOutcome.SKIPPED)))

    await dependencies.propose_and_post(target, channel_id="C1")

    assert "no LinkedIn page is saved for Acme Co" in notifier.posts[1].body


async def test_a_failed_scan_says_so_without_error_detail(
    monkeypatch, target: EnrichmentTarget
) -> None:
    notifier = _wire(monkeypatch, _Service(LinkedInScan(outcome=ScanOutcome.FAILED)))

    await dependencies.propose_and_post(target, channel_id="C1")

    assert "scan failed" in notifier.posts[1].body
    assert "Traceback" not in notifier.posts[1].body


async def test_without_a_linkedin_client_nothing_is_scanned_or_posted(
    monkeypatch, target: EnrichmentTarget
) -> None:
    service = _Service(LinkedInScan())
    notifier = _wire(monkeypatch, service, linkedin_configured=False)

    await dependencies.propose_and_post(target, channel_id="C1")

    assert service.scans == 0
    assert len(notifier.posts) == 1  # only the placeholder


async def test_scan_failure_leaves_the_proposal_untouched(
    monkeypatch, target: EnrichmentTarget
) -> None:
    notifier = _wire(monkeypatch, _Service(RuntimeError("apify down")))

    await dependencies.propose_and_post(target, channel_id="C1")

    assert len(notifier.updates) == 1
    assert "failed" not in notifier.updates[0].text.lower()


async def test_failed_proposal_skips_the_follow_up(monkeypatch, target: EnrichmentTarget) -> None:
    service = _Service(LinkedInScan(), propose_error=True)
    notifier = _wire(monkeypatch, service)

    await dependencies.propose_and_post(target, channel_id="C1")

    assert service.scans == 0
    assert notifier.updates[0].text == "Enrichment failed unexpectedly."


async def test_the_triggering_user_is_passed_to_the_scan(
    monkeypatch, target: EnrichmentTarget
) -> None:
    service = _Service(LinkedInScan())
    _wire(monkeypatch, service)

    await dependencies.propose_and_post(target, channel_id="C1", requested_by="U123")

    assert service.requested_by == ["U123"]


async def test_no_triggering_user_means_none_is_passed(
    monkeypatch, target: EnrichmentTarget
) -> None:
    service = _Service(LinkedInScan())
    _wire(monkeypatch, service)

    await dependencies.propose_and_post(target, channel_id="C1")

    assert service.requested_by == [None]
