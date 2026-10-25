"""PostHog implementation of `AnalyticsPort`: who asked for, unlocked and
read which report, without SQL.

Same posture as the Firecrawl client: a blank key or an SDK error is a log
line, never a failed request. `AsyncPosthog.capture` only queues, and binds
to the running loop, so `capture` here is async to keep it on uvicorn's loop
(a sync `BackgroundTasks` callable would run in a worker thread).
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from posthog import AsyncPosthog
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report_event import ReportEvent
from app.modules.lead_magnets.domain.shared.lead_event import ConsentEvent, LeadEvent

logger = logging.getLogger(__name__)

# shortcut: Docker stops the container about 10 s after SIGTERM; a slower flush loses events.
_SHUTDOWN_TIMEOUT_S = 5.0


def _replay_key(event: LeadEvent) -> str:
    return str(uuid5(NAMESPACE_URL, f"{event.event}:{event.tool}:{event.submission_id}"))


class PersonSet(BaseModel):
    name: str
    email: str
    company: str


class AnonymousReportProperties(BaseModel):
    """A report event for a visitor who did not accept tracking: no name, email,
    company or domain, and never a person."""

    model_config = ConfigDict(populate_by_name=True)

    slug: str
    report_title: str
    is_test: bool
    format: Literal["html", "pdf"] | None = None
    process_person_profile: bool = Field(default=False, alias="$process_person_profile")


class PostHogProperties(BaseModel):
    """The SDK's `properties`. `$` keys go out by alias."""

    model_config = ConfigDict(populate_by_name=True)

    slug: str
    report_title: str
    company: str
    domain: str | None
    is_test: bool
    format: Literal["html", "pdf"] | None = None
    person_set: PersonSet | None = Field(default=None, alias="$set")
    # An email nobody has confirmed must never create or edit a person.
    process_person_profile: bool | None = Field(default=None, alias="$process_person_profile")

    @classmethod
    def of(cls, event: ReportEvent, *, is_test: bool) -> "PostHogProperties":
        unlocked = event.event == "report_unlocked"
        proven = unlocked and event.email_verified
        no_person = event.event == "report_code_requested" or (unlocked and not proven)
        return cls(
            slug=event.slug,
            report_title=event.report_title,
            company=event.company,
            domain=event.domain,
            is_test=is_test,
            format=event.format,
            person_set=(
                PersonSet(name=event.name, email=event.email.lower(), company=event.company)
                if proven
                else None
            ),
            process_person_profile=False if no_person else None,
        )


class LeadProperties(BaseModel):
    """A lead event's `properties`: tool and submission id, plus a person only if consented."""

    model_config = ConfigDict(populate_by_name=True)

    tool: str
    submission_id: str
    is_test: bool
    source: Literal["email"] | None = None
    person_set: PersonSet | None = Field(default=None, alias="$set")
    process_person_profile: bool | None = Field(default=None, alias="$process_person_profile")

    @classmethod
    def of(cls, event: LeadEvent, *, is_test: bool) -> "LeadProperties":
        person = event.person
        return cls(
            tool=event.tool,
            submission_id=event.submission_id,
            is_test=is_test,
            source=event.source,
            person_set=(
                PersonSet(name=person.name, email=person.email.lower(), company=person.company)
                if person
                else None
            ),
            process_person_profile=False if person is None else None,
        )


class PostHogAnalytics:
    def __init__(self, api_key: str, *, host: str, is_test: bool) -> None:
        self._client = AsyncPosthog(api_key, host=host) if api_key else None
        self.is_test = is_test
        if self._client is None:
            logger.info("posthog_capture_skipped reason=no_api_key")

    async def capture(self, event: ReportEvent) -> None:
        if self._client is None:
            return
        if not event.identified:
            self._capture_anonymous(event)
            return
        properties = PostHogProperties.of(event, is_test=self.is_test)
        distinct_id = event.email.lower()
        try:
            if event.event == "report_unlocked" and event.email_verified and event.visitor_id:
                self._identify(distinct_id, event.visitor_id, event.at)
            self._client.capture(
                event.event,
                distinct_id=distinct_id,
                properties=properties.model_dump(by_alias=True, exclude_none=True),
                timestamp=event.at,
            )
        except Exception as exc:  # noqa: BLE001 - analytics never fails a reader
            logger.warning("posthog_capture_failed event=%s error=%s", event.event, exc)

    def _capture_anonymous(self, event: ReportEvent) -> None:
        if self._client is None:
            return
        properties = AnonymousReportProperties(
            slug=event.slug,
            report_title=event.report_title,
            is_test=self.is_test,
            format=event.format,
        )
        try:
            self._client.capture(
                event.event,
                distinct_id=event.anonymous_id or str(uuid4()),
                properties=properties.model_dump(by_alias=True, exclude_none=True),
                timestamp=event.at,
            )
        except Exception as exc:  # noqa: BLE001 - analytics never fails a reader
            logger.warning("posthog_capture_failed event=%s error=%s", event.event, exc)

    async def capture_lead(self, event: LeadEvent) -> None:
        if self._client is None:
            return
        properties = LeadProperties.of(event, is_test=self.is_test)
        person = event.person
        distinct_id = person.email.lower() if person else event.submission_id
        try:
            if person and event.visitor_id:
                self._identify(distinct_id, event.visitor_id, event.at)
            self._client.capture(
                event.event,
                distinct_id=distinct_id,
                properties=properties.model_dump(by_alias=True, exclude_none=True),
                timestamp=event.at,
                # A retried submit reuses its id, so PostHog drops the repeat.
                uuid=_replay_key(event) if event.event == "lead_submitted" else None,
            )
        except Exception as exc:  # noqa: BLE001 - analytics never fails a lead
            logger.warning("posthog_capture_failed event=%s error=%s", event.event, exc)

    async def capture_consent(self, event: ConsentEvent) -> None:
        if self._client is None:
            return
        try:
            self._client.capture(
                "consent_choice",
                # A fresh id per click: the choice is counted, the visitor never is.
                distinct_id=str(uuid4()),
                properties={
                    "choice": event.choice,
                    "is_test": self.is_test,
                    "$process_person_profile": False,
                },
                timestamp=event.at,
            )
        except Exception as exc:  # noqa: BLE001 - analytics never fails a visitor
            logger.warning("posthog_capture_failed event=consent_choice error=%s", exc)

    def _identify(self, distinct_id: str, visitor_id: str, at: datetime) -> None:
        """Merges the visitor's earlier anonymous page views into the person."""
        if self._client is not None:
            self._client.capture(
                "$identify",
                distinct_id=distinct_id,
                properties={"$anon_distinct_id": visitor_id},
                timestamp=at,
            )

    async def shutdown(self) -> None:
        if self._client is None:
            return
        try:
            await asyncio.wait_for(self._client.shutdown(), _SHUTDOWN_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - never block or fail app shutdown
            logger.warning("posthog_shutdown_failed error=%s", exc)
