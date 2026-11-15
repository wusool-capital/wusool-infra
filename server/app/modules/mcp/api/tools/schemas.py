"""The MCP's contract. Claude conversations and skills depend on these names:
add fields, never rename one or change what it means. A breaking change is a new tool."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ddl_commands import (
    AddOutcome,
    Column,
    CommitProgress,
    RecordRef,
    RowOutcome,
    RowProblem,
    UploadKind,
    UploadRow,
    columns_for,
)
from app.modules.ddl_commands import RecordDetail as DdlRecordDetail
from app.modules.ddl_commands import RecordList as DdlRecordList

FieldValue = str | float | bool | list[str] | None
Fields = Annotated[
    dict[str, FieldValue],
    Field(description="Optional extra fields by key; see the field list in the tool description."),
]
RequestId = Annotated[
    str,
    Field(
        min_length=8,
        max_length=100,
        description="A new unique id (for example a UUID) per change. Resend the same id "
        "to retry safely: the change is never made twice.",
    ),
]
_ROW_KEYS = frozenset({"org_name", "domain", "target_vertical"})


class SellerRow(BaseModel):
    org_name: str = Field(min_length=1, max_length=300, description="Company name")
    domain: str = Field(
        min_length=1, max_length=300, description="Company website or domain, e.g. acme.com"
    )
    fields: Fields = {}

    def to_upload_row(self) -> UploadRow:
        return {**self.fields, "org_name": self.org_name, "domain": self.domain}


class BuyerRow(SellerRow):
    target_vertical: str = Field(description="The buyer's vertical; one buyer per vertical")

    def to_upload_row(self) -> UploadRow:
        return {**super().to_upload_row(), "target_vertical": self.target_vertical}


class Record(BaseModel):
    model_config = ConfigDict(frozen=True)

    role_id: uuid.UUID = Field(description="buyer_role_id or seller_role_id, used to edit")
    org_attio_id: str
    org_name: str
    domains: list[str]
    target_vertical: str | None = None

    @classmethod
    def of(cls, ref: RecordRef) -> "Record":
        return cls(
            role_id=ref.role_id,
            org_attio_id=ref.org_attio_id,
            org_name=ref.org_name,
            domains=list(ref.domains),
            target_vertical=ref.target_vertical,
        )


class FindResult(BaseModel):
    records: list[Record]


class AddResult(BaseModel):
    status: Literal["added", "existing"] = Field(
        description="existing: the company already has this record, so nothing was changed"
    )
    record: Record

    @classmethod
    def of(cls, outcome: AddOutcome) -> "AddResult":
        return cls(status=outcome.status, record=Record.of(outcome.record))


class EditResult(BaseModel):
    role_id: uuid.UUID
    changed_fields: list[str]


class Problem(BaseModel):
    row: int
    field: str | None
    message: str

    @classmethod
    def of(cls, problem: RowProblem) -> "Problem":
        return cls(row=problem.row, field=problem.field, message=problem.message)


class ImportPreview(BaseModel):
    """Nothing is saved yet. With no problems, show the counts and, once the
    person says go, call confirm_import with `preview_id`."""

    accepted: bool = Field(description="False: fix every row in `problems` and send again")
    preview_id: uuid.UUID | None = None
    new: int = 0
    existing: int = Field(default=0, description="Rows already in the CRM; they'll be skipped")
    existing_rows: list[int] = []
    invalid: int = 0
    problems: list[Problem] = []


class RowResult(BaseModel):
    row: int
    reason: str | None = None

    @classmethod
    def of(cls, outcome: RowOutcome) -> "RowResult":
        return cls(row=outcome.row, reason=outcome.reason)


class ImportProgress(BaseModel):
    preview_id: uuid.UUID
    state: Literal["ready", "running", "done", "interrupted"]
    total: int = Field(description="New rows to add")
    added: int
    skipped: list[RowResult]
    failed: list[RowResult]

    @classmethod
    def of(cls, preview_id: uuid.UUID, progress: CommitProgress) -> "ImportProgress":
        return cls(
            preview_id=preview_id,
            state=progress.state,
            total=progress.total,
            added=progress.added,
            skipped=[RowResult.of(o) for o in progress.skipped],
            failed=[RowResult.of(o) for o in progress.failed],
        )


# Longer option lists stay out of tool descriptions; list_field_options returns them.
_INLINE_OPTIONS_MAX = 8


def _describe(column: Column) -> str:
    spec = column.spec
    if spec is None:
        return column.field
    line = f"- {column.field} ({spec.kind})"
    if not spec.options:
        return line
    if len(spec.options) > _INLINE_OPTIONS_MAX:
        return f"{line}: {len(spec.options)} options, see list_field_options"
    return f"{line}: one of {' | '.join(spec.options)}"


def field_guide(kind: UploadKind, *, editing: bool = False) -> str:
    """Which keys a tool takes, which are required, and the allowed values, from the same
    specs the Slack forms use. Adding (and each bulk row) needs the row keys at the top
    level of the record; editing needs only the `role_id` and the fields to change."""
    columns = columns_for(kind)
    optional = [_describe(c) for c in columns if c.field not in _ROW_KEYS]
    values = (
        "(lists for multi-select; money in USD; dates as YYYY-MM-DD). "
        "Allowed values match ignoring case:\n"
    )
    if editing:
        cannot = ", ".join(c.field for c in columns if c.field in _ROW_KEYS)
        return (
            f"Required: role_id only. Send just the fields to change; every key below is "
            f"optional ({cannot} can't be edited).\n"
            f"Keys for `fields` {values}" + "\n".join(optional)
        )
    required = [
        _describe(c) if c.spec else c.field for c in columns if c.field in _ROW_KEYS and c.required
    ]
    return (
        "Required, at the top level of the record (not inside `fields`):\n"
        + "\n".join(f"- {line.removeprefix('- ')}" for line in required)
        + f"\nEverything in `fields` is optional. Keys for `fields` {values}"
        + "\n".join(optional)
    )


# --- Benchmark peer dataset --------------------------------------------------

BenchmarkMode = Literal["sme", "tech"]
ModeParam = Annotated[
    BenchmarkMode,
    Field(description="'sme' for the sector peer sets, 'tech' for the funding-stage peer sets"),
]
AnchorList = Annotated[
    list[float],
    Field(min_length=5, max_length=5, description="[p10, p25, p50, p75, p90], rising"),
]


class PercentileEditIn(BaseModel):
    """Some of one metric's five anchors. The ones left out keep their value."""

    model_config = ConfigDict(extra="forbid")

    p10: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None

    @model_validator(mode="after")
    def _names_one(self) -> "PercentileEditIn":
        if all(v is None for v in (self.p10, self.p25, self.p50, self.p75, self.p90)):
            raise ValueError("name at least one of p10, p25, p50, p75, p90")
        return self


AnchorsIn = AnchorList | PercentileEditIn
UpdatedBy = Annotated[str, Field(description="Who last changed this, by name ('seed' if never)")]
UpdatedAt = Annotated[datetime, Field(description="When it was last changed")]


class BandOut(BaseModel):
    code: str
    label: str
    max_usd: float | None = Field(description="Revenue ceiling in USD; null on the top band")
    ebitda_adj: float = Field(description="Points added to the sector's EBITDA margin anchors")
    rev_emp_mult: float = Field(description="Multiplies the revenue-per-employee anchors")
    rent_mult: float = Field(description="Multiplies the premises-cost anchors")
    updated_by: UpdatedBy
    updated_at: UpdatedAt


class MetricOut(BaseModel):
    key: str
    label: str
    unit: str
    weight: int = Field(description="Share of the score; a mode's weights add up to 100")
    updated_by: UpdatedBy
    updated_at: UpdatedAt


class PeerCutSummary(BaseModel):
    mode: BenchmarkMode
    key: str
    label: str
    sample_size: int | None
    multi_site: bool
    b2b: bool
    updated_by: UpdatedBy
    updated_at: UpdatedAt


class PeerCutOut(PeerCutSummary):
    anchors: dict[str, AnchorList] = Field(
        description="Percentile anchors [p10, p25, p50, p75, p90] by metric key"
    )


class BenchmarkOverview(BaseModel):
    dataset_updated_at: datetime = Field(description="The most recent change to any row")
    sme_metrics: list[MetricOut]
    tech_metrics: list[MetricOut]
    bands: list[BandOut]
    peer_cuts: list[PeerCutSummary]


class BandList(BaseModel):
    bands: list[BandOut]


class MetricList(BaseModel):
    mode: BenchmarkMode
    metrics: list[MetricOut]


class RecordDetail(Record):
    fields: dict[str, FieldValue] = Field(
        description="Every field, keyed like edit_buyer/edit_seller's `fields`; null when unset"
    )

    @classmethod
    def of_detail(cls, detail: DdlRecordDetail) -> "RecordDetail":
        return cls(**Record.of(detail).model_dump(), fields=dict(detail.fields))


class RecordList(BaseModel):
    records: list[Record]
    truncated: bool = Field(description="True when more records match: narrow the filters")

    @classmethod
    def of(cls, found: DdlRecordList) -> "RecordList":
        return cls(records=[Record.of(r) for r in found.records], truncated=found.truncated)


class Gap(BaseModel):
    criterion: str
    stored: str = Field(description="What the profile holds")
    stated: str | None = None


class BuyerCheck(BaseModel):
    role_id: uuid.UUID
    clear: bool = Field(description="True when nothing is missing or in conflict")
    conflicts: list[Gap]
    missing: list[Gap]
    message: str = Field(description="The same summary /check-buyer shows in Slack")


class FieldOption(BaseModel):
    key: str
    label: str
    kind: str
    required: bool
    options: list[str] = Field(description="Allowed values; empty for free-form fields")


class FieldOptions(BaseModel):
    kind: UploadKind
    fields: list[FieldOption]

    @classmethod
    def of(cls, kind: UploadKind) -> "FieldOptions":
        return cls(
            kind=kind,
            fields=[
                FieldOption(
                    key=c.field,
                    label=c.label,
                    kind=c.spec.kind if c.spec else "text",
                    required=c.required,
                    options=list(c.spec.options) if c.spec else [],
                )
                for c in columns_for(kind)
            ],
        )
