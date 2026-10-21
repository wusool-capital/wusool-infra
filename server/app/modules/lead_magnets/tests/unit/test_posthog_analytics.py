"""PostHog report events: the right properties per event, a person only for a
proven email, and never an exception reaching a reader. The SDK client is
swapped for a fake, as `test_firecrawl_client.py` does."""

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from app.modules.lead_magnets.domain.insights_report.report_event import (
    ReportEvent,
    ReportEventName,
)
from app.modules.lead_magnets.domain.shared.lead_event import LeadEvent, LeadEventName, LeadPerson
from app.modules.lead_magnets.providers.posthog import client as posthog_client
from app.modules.lead_magnets.providers.posthog.client import PostHogAnalytics

_AT = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)

Properties = dict[str, str | bool | dict[str, str]]


def _event(name: ReportEventName, *, domain: str | None = "acme.ae") -> ReportEvent:
    return ReportEvent(
        event=name,
        name="Dana",
        email="Dana@Acme.ae",
        company="Acme",
        domain=domain,
        slug="buyouts-in-the-gcc",
        report_title="Buyouts in the GCC",
        at=_AT,
    )


@dataclass(frozen=True)
class _Call:
    event: str
    distinct_id: str
    properties: Properties
    timestamp: datetime
    uuid: str | None = None


@dataclass
class _FakeSdk:
    raises: Exception | None = None
    shutdown_delay_s: float = 0
    calls: list[_Call] = field(default_factory=list)
    shut_down: bool = False

    def capture(
        self,
        event: str,
        *,
        distinct_id: str,
        properties: Properties,
        timestamp: datetime,
        uuid: str | None = None,
    ) -> str:
        if self.raises:
            raise self.raises
        self.calls.append(_Call(event, distinct_id, properties, timestamp, uuid))
        return "uuid"

    async def shutdown(self) -> None:
        await asyncio.sleep(self.shutdown_delay_s)
        self.shut_down = True


def _analytics(sdk: _FakeSdk, *, is_test: bool = False) -> PostHogAnalytics:
    analytics = PostHogAnalytics("phc_test", host="https://eu.i.posthog.com", is_test=is_test)
    analytics._client = sdk
    return analytics


async def test_unlock_sets_the_person_and_carries_the_report() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk, is_test=True).capture(_event("report_unlocked"))

    (call,) = sdk.calls
    assert call.event == "report_unlocked"
    assert call.distinct_id == "dana@acme.ae"
    assert call.timestamp == _AT
    assert call.properties == {
        "slug": "buyouts-in-the-gcc",
        "report_title": "Buyouts in the GCC",
        "company": "Acme",
        "domain": "acme.ae",
        "is_test": True,
        "$set": {"name": "Dana", "email": "dana@acme.ae", "company": "Acme"},
    }


async def test_a_code_request_never_creates_or_edits_a_person() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(_event("report_code_requested"))

    properties = sdk.calls[0].properties
    assert properties["$process_person_profile"] is False
    assert "$set" not in properties


async def test_an_unlock_without_a_proven_email_never_edits_a_person() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(replace(_event("report_unlocked"), email_verified=False))

    properties = sdk.calls[0].properties
    assert properties["$process_person_profile"] is False
    assert "$set" not in properties


async def test_a_view_carries_its_format_and_no_person_set() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(replace(_event("report_viewed"), format="pdf"))

    properties = sdk.calls[0].properties
    assert properties["format"] == "pdf"
    assert "$set" not in properties and "$process_person_profile" not in properties


async def test_a_free_mail_reader_has_no_domain_property() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(_event("report_unlocked", domain=None))

    assert "domain" not in sdk.calls[0].properties


async def test_a_blank_key_sends_nothing() -> None:
    analytics = PostHogAnalytics("", host="https://eu.i.posthog.com", is_test=False)

    assert analytics._client is None
    await analytics.capture(_event("report_unlocked"))
    await analytics.shutdown()


async def test_an_sdk_error_is_swallowed() -> None:
    await _analytics(_FakeSdk(raises=RuntimeError("down"))).capture(_event("report_viewed"))


async def test_shutdown_flushes_the_sdk() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).shutdown()

    assert sdk.shut_down


async def test_a_stuck_flush_is_cut_off_instead_of_blocking_shutdown(monkeypatch) -> None:
    monkeypatch.setattr(posthog_client, "_SHUTDOWN_TIMEOUT_S", 0.01)
    sdk = _FakeSdk(shutdown_delay_s=5)

    await _analytics(sdk).shutdown()

    assert not sdk.shut_down


def _lead(
    name: LeadEventName = "lead_submitted",
    *,
    person: LeadPerson | None = None,
    visitor_id: str | None = None,
) -> LeadEvent:
    return LeadEvent(
        event=name,
        tool="readiness",
        submission_id="sub-1",
        at=_AT,
        source="email" if name == "book_call_clicked" else None,
        person=person,
        visitor_id=visitor_id,
    )


_DANA = LeadPerson(name="Dana", email="Dana@Acme.ae", company="Acme")


async def test_an_anonymous_lead_carries_no_email_and_creates_no_person() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk, is_test=True).capture_lead(_lead())

    (call,) = sdk.calls
    assert call.event == "lead_submitted"
    assert call.distinct_id == "sub-1", "keyed on the random submission id, never an email"
    assert call.properties == {
        "tool": "readiness",
        "submission_id": "sub-1",
        "is_test": True,
        "$process_person_profile": False,
    }


async def test_a_consented_lead_sets_the_person_and_links_the_visitor() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture_lead(_lead(person=_DANA, visitor_id="anon-123"))

    identify, lead = sdk.calls
    assert identify.event == "$identify"
    assert identify.distinct_id == "dana@acme.ae"
    assert identify.properties == {"$anon_distinct_id": "anon-123"}
    assert lead.event == "lead_submitted"
    assert lead.distinct_id == "dana@acme.ae"
    assert lead.properties["$set"] == {"name": "Dana", "email": "dana@acme.ae", "company": "Acme"}
    assert "$process_person_profile" not in lead.properties


async def test_a_consented_lead_without_a_visitor_id_sends_no_identify() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture_lead(_lead(person=_DANA))

    assert [c.event for c in sdk.calls] == ["lead_submitted"]


async def test_a_retried_submit_reuses_one_event_id_so_posthog_drops_the_repeat() -> None:
    sdk = _FakeSdk()
    analytics = _analytics(sdk)
    await analytics.capture_lead(_lead())
    await analytics.capture_lead(_lead())

    first, second = sdk.calls
    assert first.uuid is not None and first.uuid == second.uuid


async def test_every_book_call_click_counts() -> None:
    sdk = _FakeSdk()
    analytics = _analytics(sdk)
    await analytics.capture_lead(_lead("book_call_clicked"))
    await analytics.capture_lead(_lead("book_call_clicked"))

    assert [c.uuid for c in sdk.calls] == [None, None]
    assert sdk.calls[0].properties["source"] == "email"


async def test_an_sdk_error_never_fails_a_lead() -> None:
    await _analytics(_FakeSdk(raises=RuntimeError("down"))).capture_lead(_lead(person=_DANA))


async def test_a_blank_key_sends_no_lead_events() -> None:
    analytics = PostHogAnalytics("", host="https://eu.i.posthog.com", is_test=False)

    await analytics.capture_lead(_lead(person=_DANA, visitor_id="anon-123"))


async def test_a_verified_unlock_links_the_visitor_to_the_person() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(replace(_event("report_unlocked"), visitor_id="anon-9"))

    identify, unlocked = sdk.calls
    assert identify.event == "$identify" and identify.distinct_id == "dana@acme.ae"
    assert identify.properties == {"$anon_distinct_id": "anon-9"}
    assert unlocked.event == "report_unlocked"


async def test_an_unverified_unlock_never_links_a_visitor() -> None:
    sdk = _FakeSdk()
    event = replace(_event("report_unlocked"), email_verified=False, visitor_id="anon-9")
    await _analytics(sdk).capture(event)

    assert [c.event for c in sdk.calls] == ["report_unlocked"]
