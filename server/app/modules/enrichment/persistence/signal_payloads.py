"""Typed `signals.payload` models for LinkedIn. These hold the personal data
(names, titles, post text) so the append-only `activities` row never has to.
"""

import uuid
from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, JsonValue

from app.modules.enrichment.domain.linkedin import JobChange, LinkedInPost


class PostSignalPayload(BaseModel):
    kind: Literal["post"] = "post"
    text: str
    post_url: str
    author_name: str | None = None
    author_url: str | None = None


class JobChangeSignalPayload(BaseModel):
    kind: Literal["job_change"] = "job_change"
    person_attio_id: str
    contact_name: str
    profile_url: str
    title_changed: bool
    company_changed: bool
    previous_title: str | None = None
    new_title: str | None = None
    previous_company: str | None = None
    new_company: str | None = None


SignalPayload = PostSignalPayload | JobChangeSignalPayload

# A `signals.payload` value as the JSONB column takes it.
JsonPayload = dict[str, JsonValue]


class SignalInsert(TypedDict):
    """The columns of one `signals` row, in the shape the multi-row INSERT takes."""

    org_attio_id: str
    source: str
    external_id: str
    payload: JsonPayload
    ts: datetime
    source_cite: str
    linkedin_scan_id: uuid.UUID


def dump_payload(payload: SignalPayload) -> JsonPayload:
    return payload.model_dump(mode="json")


def post_payload(post: LinkedInPost) -> PostSignalPayload:
    return PostSignalPayload(
        text=post.text,
        post_url=post.url,
        author_name=post.author_name,
        author_url=post.author_url,
    )


def job_change_payload(change: JobChange) -> JobChangeSignalPayload:
    return JobChangeSignalPayload(
        person_attio_id=change.contact.person_attio_id,
        contact_name=change.contact.name,
        profile_url=change.source_url,
        title_changed=change.title_changed,
        company_changed=change.company_changed,
        previous_title=change.contact.job_title,
        new_title=change.profile.current_title,
        previous_company=change.contact.company_name,
        new_company=change.profile.current_company,
    )
