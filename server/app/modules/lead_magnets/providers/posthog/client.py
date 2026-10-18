"""PostHog implementation of `AnalyticsPort`: who asked for, unlocked and
read which report, without SQL.

Same posture as the Firecrawl client: a blank key or an SDK error is a log
line, never a failed request. `AsyncPosthog.capture` only queues, and binds
to the running loop, so `capture` here is async to keep it on uvicorn's loop
(a sync `BackgroundTasks` callable would run in a worker thread).
"""

import asyncio
import logging
from typing import Literal

from posthog import AsyncPosthog
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report_event import ReportEvent

logger = logging.getLogger(__name__)

# shortcut: Docker stops the container about 10 s after SIGTERM; a slower flush loses events.
_SHUTDOWN_TIMEOUT_S = 5.0


class PersonSet(BaseModel):
    name: str
    email: str
    company: str


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
        return cls(
            slug=event.slug,
            report_title=event.report_title,
            company=event.company,
            domain=event.domain,
            is_test=is_test,
            format=event.format,
            person_set=(
                PersonSet(name=event.name, email=event.email, company=event.company)
                if unlocked
                else None
            ),
            process_person_profile=(False if event.event == "report_code_requested" else None),
        )


class PostHogAnalytics:
    def __init__(self, api_key: str, *, host: str, is_test: bool) -> None:
        self._client = AsyncPosthog(api_key, host=host) if api_key else None
        self._is_test = is_test

    async def capture(self, event: ReportEvent) -> None:
        if self._client is None:
            logger.info("posthog_capture_skipped reason=no_api_key event=%s", event.event)
            return
        properties = PostHogProperties.of(event, is_test=self._is_test)
        try:
            self._client.capture(
                event.event,
                distinct_id=event.email.lower(),
                properties=properties.model_dump(by_alias=True, exclude_none=True),
                timestamp=event.at,
            )
        except Exception as exc:  # noqa: BLE001 - analytics never fails a reader
            logger.warning("posthog_capture_failed event=%s error=%s", event.event, exc)

    async def shutdown(self) -> None:
        if self._client is None:
            return
        try:
            await asyncio.wait_for(self._client.shutdown(), _SHUTDOWN_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - never block or fail app shutdown
            logger.warning("posthog_shutdown_failed error=%s", exc)
