"""PostHog report events: the right properties per event, a person only for a
proven email, and never an exception reaching a reader. The SDK client is
swapped for a fake, as `test_firecrawl_client.py` does."""

from datetime import UTC, datetime

from app.modules.lead_magnets.domain.insights_report.report_event import (
    ReportEvent,
    ReportEventName,
)
from app.modules.lead_magnets.providers.posthog.client import PostHogAnalytics

_AT = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def _event(name: ReportEventName, **overrides: str) -> ReportEvent:
    fields = {
        "name": "Dana",
        "email": "Dana@Acme.ae",
        "company": "Acme",
        "domain": "acme.ae",
        "slug": "buyouts-in-the-gcc",
        "report_title": "Buyouts in the GCC",
    }
    return ReportEvent(event=name, at=_AT, **{**fields, **overrides})


class _FakeSdk:
    def __init__(self, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list[dict] = []
        self.shut_down = False

    def capture(self, event: str, **kwargs) -> str:
        if self.raises:
            raise self.raises
        self.calls.append({"event": event, **kwargs})
        return "uuid"

    async def shutdown(self) -> None:
        self.shut_down = True


def _analytics(sdk: _FakeSdk, *, is_test: bool = False) -> PostHogAnalytics:
    analytics = PostHogAnalytics("phc_test", host="https://eu.i.posthog.com", is_test=is_test)
    analytics._client = sdk
    return analytics


async def test_unlock_sets_the_person_and_carries_the_report() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk, is_test=True).capture(_event("report_unlocked"))

    (call,) = sdk.calls
    assert call["event"] == "report_unlocked"
    assert call["distinct_id"] == "dana@acme.ae"
    assert call["timestamp"] == _AT
    assert call["properties"] == {
        "slug": "buyouts-in-the-gcc",
        "report_title": "Buyouts in the GCC",
        "company": "Acme",
        "domain": "acme.ae",
        "is_test": True,
        "$set": {"name": "Dana", "email": "Dana@Acme.ae", "company": "Acme"},
    }


async def test_a_code_request_never_creates_or_edits_a_person() -> None:
    sdk = _FakeSdk()
    await _analytics(sdk).capture(_event("report_code_requested"))

    properties = sdk.calls[0]["properties"]
    assert properties["$process_person_profile"] is False
    assert "$set" not in properties


async def test_a_view_carries_its_format_and_no_person_set() -> None:
    sdk = _FakeSdk()
    event = ReportEvent(**{**_event("report_viewed").__dict__, "format": "pdf"})
    await _analytics(sdk).capture(event)

    properties = sdk.calls[0]["properties"]
    assert properties["format"] == "pdf"
    assert "$set" not in properties and "$process_person_profile" not in properties


async def test_a_free_mail_reader_has_no_domain_property() -> None:
    sdk = _FakeSdk()
    event = ReportEvent(**{**_event("report_unlocked").__dict__, "domain": None})
    await _analytics(sdk).capture(event)

    assert "domain" not in sdk.calls[0]["properties"]


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
