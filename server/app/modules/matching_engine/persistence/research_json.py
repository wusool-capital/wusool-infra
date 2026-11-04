"""The stored shape of a candidate's `metadata.research`, parsed at the
persistence boundary so nothing inward sees raw JSON."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.matching_engine.domain.matching.research import (
    ResearchField,
    ResearchJobChange,
    ResearchLinkedIn,
    ResearchPost,
    ResearchRecord,
    ResearchValue,
)
from app.modules.utilities.domain.json_types import JsonObject


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Field(_Model):
    name: str
    target: Literal["organization", "seller_role"]
    proposed: ResearchValue
    display: str
    confidence: float
    source_url: str
    rationale: str


class _Post(_Model):
    url: str
    text: str
    author_name: str | None = None
    posted_at: datetime | None = None


class _JobChange(_Model):
    name: str
    title: str | None = None
    company: str | None = None
    source_url: str


class _LinkedIn(_Model):
    outcome: Literal["completed", "skipped", "failed"]
    posts: list[_Post] = []
    job_changes: list[_JobChange] = []
    contacts_scanned: int = 0
    contacts_without_linkedin: int = 0


class _Research(_Model):
    claimed_at: datetime
    outcome: Literal["done", "failed"] | None = None
    error: str | None = None
    fields: list[_Field] = []
    linkedin: _LinkedIn | None = None
    saved_fields: list[str] = []
    skipped: bool = False
    saving_at: datetime | None = None


def research_from_dict(data: JsonObject | None) -> ResearchRecord | None:
    if not data:
        return None
    try:
        stored = _Research.model_validate(data)
    except ValidationError:
        return None
    linkedin = stored.linkedin
    return ResearchRecord(
        claimed_at=stored.claimed_at,
        outcome=stored.outcome,
        error=stored.error,
        fields=tuple(ResearchField(**f.model_dump()) for f in stored.fields),
        linkedin=ResearchLinkedIn(
            outcome=linkedin.outcome,
            posts=tuple(ResearchPost(**p.model_dump()) for p in linkedin.posts),
            job_changes=tuple(ResearchJobChange(**j.model_dump()) for j in linkedin.job_changes),
            contacts_scanned=linkedin.contacts_scanned,
            contacts_without_linkedin=linkedin.contacts_without_linkedin,
        )
        if linkedin
        else None,
        saved_fields=tuple(stored.saved_fields),
        skipped=stored.skipped,
        saving_at=stored.saving_at,
    )


def research_to_dict(record: ResearchRecord) -> JsonObject:
    return _Research.model_validate(record, from_attributes=True).model_dump(mode="json")
