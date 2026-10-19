"""The LinkedIn thread reply must never cost the proposal: it is posted
after the proposal update, in the placeholder's thread, and its own
failures are swallowed.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from slack_sdk.models.blocks import Block

from app.modules.enrichment.api import dependencies
from app.modules.enrichment.domain.linkedin import LinkedInPost, LinkedInScan
from app.modules.enrichment.domain.proposals import EnrichmentProposal
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind


@dataclass(frozen=True)
class _Message:
    channel: str
    text: str
    thread_ts: str | None = None


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
        self.posts.append(_Message(channel=channel, text=text, thread_ts=thread_ts))
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

    async def propose(self, target: EnrichmentTarget) -> EnrichmentProposal:
        if self._propose_error:
            raise RuntimeError("boom")
        return EnrichmentProposal(target=target, values=(), generated_by_model="m")

    async def scan_linkedin(self, target: EnrichmentTarget) -> LinkedInScan:
        self.scans += 1
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


def _wire(monkeypatch, service: _Service) -> _Notifier:
    notifier = _Notifier()
    monkeypatch.setattr(dependencies, "slack_notifier", lambda: notifier)
    monkeypatch.setattr(dependencies, "enrichment_service", lambda: service)
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


async def test_empty_scan_posts_nothing(monkeypatch, target: EnrichmentTarget) -> None:
    notifier = _wire(monkeypatch, _Service(LinkedInScan()))

    await dependencies.propose_and_post(target, channel_id="C1")

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
