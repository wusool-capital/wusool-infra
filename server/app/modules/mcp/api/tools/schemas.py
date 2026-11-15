"""The MCP's contract. Claude conversations and skills depend on these names:
add fields, never rename one or change what it means. A breaking change is a new tool."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


def field_guide(kind: UploadKind) -> str:
    """Every key `fields` accepts, from the same specs the Slack forms use."""
    lines = [
        _describe(c) for c in columns_for(kind) if c.field not in _ROW_KEYS - {"target_vertical"}
    ]
    return (
        "Field keys for `fields` (lists for multi-select; money in USD; dates as YYYY-MM-DD). "
        "Allowed values match ignoring case:\n" + "\n".join(lines)
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


class BandOut(BaseModel):
    id: str
    label: str
    max_usd: float | None = Field(description="Revenue ceiling in USD; null on the top band")
    ebitda_adj: float = Field(description="Points added to the sector's EBITDA margin anchors")
    rev_emp_mult: float = Field(description="Multiplies the revenue-per-employee anchors")
    rent_mult: float = Field(description="Multiplies the premises-cost anchors")


class MetricOut(BaseModel):
    key: str
    label: str
    unit: str
    weight: int = Field(description="Share of the score; a mode's weights add up to 100")


class PeerCutSummary(BaseModel):
    mode: BenchmarkMode
    key: str
    label: str
    sample_size: int | None
    multi_site: bool
    b2b: bool


class PeerCutOut(PeerCutSummary):
    anchors: dict[str, AnchorList] = Field(
        description="Percentile anchors [p10, p25, p50, p75, p90] by metric key"
    )


class BenchmarkOverview(BaseModel):
    dataset_version: int
    sme_metrics: list[MetricOut]
    tech_metrics: list[MetricOut]
    bands: list[BandOut]
    peer_cuts: list[PeerCutSummary]


class PeerCutEdited(BaseModel):
    peer_cut: PeerCutOut
    dataset_version: int


class BandsEdited(BaseModel):
    bands: list[BandOut]
    dataset_version: int


class WeightsEdited(BaseModel):
    mode: BenchmarkMode
    weights: dict[str, int]
    dataset_version: int


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
