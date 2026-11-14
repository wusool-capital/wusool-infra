"""Bulk upload of buyers and sellers for MCP v1: `preview_*` validates and
dedupes and writes nothing, `commit` adds the new rows in the background through
`write_buyer_add` / `write_seller_add` (Attio first, then Postgres), `status`
reports progress.

Rows are flat: `org_name`, `domain`, plus any organization or role field name
from the Slack add forms. A company already in the CRM is skipped, never
updated: our data wins.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.models import BuyerRole, SellerRole
from app.modules.ddl_commands.api.bulk_columns import canonical_value, routes_for
from app.modules.ddl_commands.api.bulk_store import (
    MAX_ROWS,
    CommitProgress,
    InMemoryPreviewStore,
    InvokedVia,
    PlannedRow,
    PreviewStore,
    RowOutcome,
    StoredPreview,
    UploadKind,
)
from app.modules.ddl_commands.api.buyer_write import write_buyer_add
from app.modules.ddl_commands.api.buyers import BuyerUpdate
from app.modules.ddl_commands.api.dependencies import (
    ddl_commands_service,
    find_organization_by_domains,
    resolve_organization,
)
from app.modules.ddl_commands.api.organizations import OrganizationUpdate
from app.modules.ddl_commands.api.schemas import FieldSpec, PrefillValue
from app.modules.ddl_commands.api.seller_write import write_seller_add
from app.modules.ddl_commands.api.sellers import SellerUpdate
from app.modules.ddl_commands.api.slack.views.dynamic_fields import normalize_prefill
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.buyers import BuyerAlreadyExistsError
from app.modules.ddl_commands.application.sellers import SellerAlreadyExistsError
from app.modules.discovery.domain.drafts import company_hostname
from app.modules.utilities import get_shared_task_runner
from app.modules.utilities.domain.safe_errors import describe_error

logger = logging.getLogger(__name__)

UploadRow = dict[str, PrefillValue | None]
OnDone = Callable[[CommitProgress], Awaitable[None]]

_ROW_KEYS = frozenset({"org_name", "domain"})

_store: PreviewStore = InMemoryPreviewStore()
# Held across a row's re-check and write, so two commits can't both create one new company.
write_lock = asyncio.Lock()


class BulkUploadError(Exception):
    pass


class InvalidUploadError(BulkUploadError):
    pass


class PreviewNotFoundError(BulkUploadError):
    pass


ProblemKind = Literal["required", "unknown_field", "not_allowed", "invalid", "duplicate"]


class RowProblem(BaseModel):
    """What is wrong with one row. `message` is complete on its own, for Claude.
    The other fields let any caller (the Slack report) word it differently without
    reading the message."""

    model_config = ConfigDict(frozen=True)

    row: int  # 1-based position in the list, or the spreadsheet line for a file
    message: str
    kind: ProblemKind
    field: str | None = None  # the row key the problem is about
    error_type: str | None = None  # for `invalid`: the validation error's type
    duplicate_of: int | None = None  # for `duplicate`: the earlier row


class PreviewResult(BaseModel):
    """Every row is valid. `existing` rows are already in the CRM and will be skipped."""

    model_config = ConfigDict(frozen=True)

    preview_id: uuid.UUID
    new: int
    existing: int
    existing_rows: tuple[int, ...]


class RejectedUpload(BaseModel):
    """At least one row is invalid. The whole upload is refused: nothing was
    stored, so there is no preview id and nothing to commit. Fix the rows named
    in `problems` and send the list again."""

    model_config = ConfigDict(frozen=True)

    invalid: int
    problems: tuple[RowProblem, ...]


@dataclass(frozen=True)
class RowMatch:
    org_attio_id: str | None
    exists: bool


@dataclass(frozen=True)
class _Checked:
    valid: tuple[PlannedRow, ...]
    problems: tuple[RowProblem, ...]
    invalid: int


async def preview_buyers(
    rows: Sequence[UploadRow],
    *,
    row_numbers: Sequence[int] | None = None,
    invoked_via: InvokedVia = "mcp",
) -> PreviewResult | RejectedUpload:
    """All or nothing: any invalid row rejects the whole list. `row_numbers` are the
    spreadsheet lines to report, for an uploaded file; otherwise rows count from 1."""
    return await _preview("buyer", rows, row_numbers, invoked_via)


async def preview_sellers(
    rows: Sequence[UploadRow],
    *,
    row_numbers: Sequence[int] | None = None,
    invoked_via: InvokedVia = "mcp",
) -> PreviewResult | RejectedUpload:
    return await _preview("seller", rows, row_numbers, invoked_via)


def find_row_problems(
    kind: UploadKind, rows: Sequence[UploadRow], row_numbers: Sequence[int]
) -> tuple[RowProblem, ...]:
    """What is wrong with these rows, without touching the database."""
    return _validate(kind, rows, row_numbers).problems


def status(preview_id: uuid.UUID) -> CommitProgress:
    progress = _store.progress(preview_id)
    if progress is None:
        raise PreviewNotFoundError(str(preview_id))
    return progress


def commit(
    preview_id: uuid.UUID, *, requested_by: str | None, on_done: OnDone | None = None
) -> CommitProgress:
    """Starts the add in the background and returns at once; poll `status`, or
    pass `on_done` to be called with the final progress. A commit already running
    is not started twice. After it finishes, calling again re-checks every row,
    so only rows still missing are added.
    """
    preview = _store.get(preview_id)
    if preview is None:
        raise PreviewNotFoundError(str(preview_id))
    current = status(preview_id)
    if current.state == "running":
        return current
    started = preview.progress("running")
    _store.set_progress(preview_id, started)
    get_shared_task_runner().run(
        lambda: run_commit(preview, requested_by, on_done), name=f"bulk-upload-{preview_id}"
    )
    return started


async def run_commit(
    preview: StoredPreview, requested_by: str | None, on_done: OnDone | None = None
) -> None:
    progress = preview.progress("running")
    try:
        for row in preview.rows:
            outcome = await _commit_row(preview.kind, row, requested_by, preview.invoked_via)
            progress = progress.record(outcome)
            _store.set_progress(preview.id, progress)
    except BaseException:
        # Cancelled mid-batch (shutdown): mark it so a new commit may resume.
        _store.set_progress(preview.id, progress.model_copy(update={"state": "interrupted"}))
        raise
    finished = progress.model_copy(update={"state": "done"})
    _store.set_progress(preview.id, finished)
    if on_done is not None:
        try:
            await on_done(finished)
        except Exception:
            # The rows are already added; a failed notice must not look like a failed commit.
            logger.exception("bulk_upload_on_done_failed preview_id=%s", preview.id)


def _validate(
    kind: UploadKind, rows: Sequence[UploadRow], row_numbers: Sequence[int] | None
) -> _Checked:
    """Pure: no database. Rows are numbered 1..n unless the caller says which
    spreadsheet line each came from."""
    if not 1 <= len(rows) <= MAX_ROWS:
        raise InvalidUploadError(f"send between 1 and {MAX_ROWS} rows, got {len(rows)}")
    numbers = row_numbers if row_numbers is not None else range(1, len(rows) + 1)
    if len(numbers) != len(rows):
        raise InvalidUploadError("row_numbers must have one number per row")

    valid: list[PlannedRow] = []
    problems: list[RowProblem] = []
    invalid = 0
    seen: dict[tuple[str, str | None], int] = {}
    for number, raw in zip(numbers, rows, strict=True):
        parsed = parse_row(kind, number, raw)
        if isinstance(parsed, list):
            invalid += 1
            problems.extend(parsed)
            continue
        key = (parsed.domain, _vertical(parsed) if kind == "buyer" else None)
        if key in seen:
            invalid += 1
            problems.append(
                RowProblem(
                    row=number,
                    kind="duplicate",
                    duplicate_of=seen[key],
                    message=f"duplicate of row {seen[key]}",
                )
            )
            continue
        seen[key] = number
        valid.append(parsed)
    return _Checked(tuple(valid), tuple(problems), invalid)


async def _preview(
    kind: UploadKind,
    rows: Sequence[UploadRow],
    row_numbers: Sequence[int] | None,
    invoked_via: InvokedVia,
) -> PreviewResult | RejectedUpload:
    checked = _validate(kind, rows, row_numbers)
    if checked.invalid:
        # Before any database lookup: the whole upload is already refused.
        return RejectedUpload(invalid=checked.invalid, problems=checked.problems)

    # Splits the valid rows into new and already in the CRM, and stores the new ones.
    planned: list[PlannedRow] = []
    existing_rows: list[int] = []
    for row in checked.valid:
        # shortcut: one lookup per row (indexed), fine at the 1,000-row cap; batch if it grows.
        if (await match_row(kind, row)).exists:
            existing_rows.append(row.index)
        else:
            planned.append(row)

    preview = StoredPreview(
        id=uuid.uuid4(),
        kind=kind,
        rows=tuple(planned),
        invoked_via=invoked_via,
        existing_rows=tuple(existing_rows),
    )
    _store.save(preview)
    return PreviewResult(
        preview_id=preview.id,
        new=len(planned),
        existing=len(existing_rows),
        existing_rows=tuple(existing_rows),
    )


@dataclass(frozen=True)
class RoutedFields:
    org_extracted: UploadRow
    role_extracted: UploadRow
    problems: tuple[RowProblem, ...]


def _problem(
    index: int, kind: ProblemKind, field: str, message: str, error_type: str | None = None
) -> RowProblem:
    return RowProblem(row=index, kind=kind, field=field, message=message, error_type=error_type)


def route_fields(
    kind: UploadKind, index: int, raw: UploadRow, *, own_keys: frozenset[str] = frozenset()
) -> RoutedFields:
    """Splits a flat row into organization and role values, checked as the Slack
    forms check them. `own_keys` are the caller's, so not reported as unknown."""
    routes = routes_for(kind)
    fields = {key: route.spec for key, route in routes.items()}
    problems = [
        _problem(index, "unknown_field", k, f"unknown field '{k}'")
        for k in sorted(raw)
        if k not in fields and k not in own_keys
    ]

    # The same spelling rules for a file's rows and for Claude's.
    given = {
        k: canonical_value(fields[k], v) for k, v in raw.items() if k in fields and v is not None
    }
    normalized = normalize_prefill(given, fields, warn_on_drop=False)
    # A silently dropped value, or a trimmed list, would be lost data, so say so.
    problems.extend(
        _problem(index, "not_allowed", k, _not_allowed(k, fields[k]))
        for k, v in given.items()
        if k not in normalized or (isinstance(v, list) and normalized[k] != v)
    )
    org_extracted: UploadRow = {
        routes[k].name: v for k, v in normalized.items() if routes[k].target == "org"
    }
    role_extracted: UploadRow = {
        routes[k].name: v for k, v in normalized.items() if routes[k].target == "role"
    }
    role_model = BuyerUpdate if kind == "buyer" else SellerUpdate
    keys = {(r.target, r.name): r.key for r in routes.values()}
    for target, model, extracted in (
        ("org", OrganizationUpdate, org_extracted),
        ("role", role_model, role_extracted),
    ):
        try:
            model.model_validate(extracted)
        except ValidationError as exc:
            # Location and type only, as messages can quote values. Keys are the row's own.
            for e in exc.errors():
                key = keys.get((target, str(e["loc"][0])), ".".join(map(str, e["loc"])))
                message = f"invalid '{key}' ({e['type']})"
                problems.append(_problem(index, "invalid", key, message, error_type=e["type"]))
    return RoutedFields(org_extracted, role_extracted, tuple(problems))


def parse_row(kind: UploadKind, index: int, raw: UploadRow) -> PlannedRow | list[RowProblem]:
    problems: list[RowProblem] = []
    org_name = raw.get("org_name")
    if not isinstance(org_name, str) or not org_name.strip():
        problems.append(_problem(index, "required", "org_name", "org_name is required"))
    host = host_of(raw.get("domain"))
    if host is None:
        message = "domain is required (a company website or domain)"
        problems.append(_problem(index, "required", "domain", message))
    if kind == "buyer" and not raw.get("target_vertical"):
        message = "target_vertical is required"
        problems.append(_problem(index, "required", "target_vertical", message))
    routed = route_fields(kind, index, raw, own_keys=_ROW_KEYS)
    problems.extend(routed.problems)
    org_extracted, role_extracted = routed.org_extracted, routed.role_extracted

    if problems or not isinstance(org_name, str) or host is None:
        return problems
    return PlannedRow(
        index=index,
        org_name=org_name.strip(),
        domain=host,
        org_extracted=org_extracted,
        role_extracted=role_extracted,
    )


def _not_allowed(key: str, spec: FieldSpec) -> str:
    """Names the allowed values, so the sender can fix the row and send it again."""
    return f"value not allowed for '{key}'. Allowed: {'; '.join(spec.options)}"


def host_of(value: PrefillValue | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    host = company_hostname(url if "//" in url else f"https://{url}")
    return host.lower().removeprefix("www.") if host else None


def _vertical(row: PlannedRow) -> str | None:
    vertical = row.role_extracted.get("target_vertical")
    return vertical if isinstance(vertical, str) else None


async def match_row(kind: UploadKind, row: PlannedRow) -> RowMatch:
    org = await find_organization_by_domains([row.domain, f"www.{row.domain}"])
    if org is None:
        return RowMatch(None, False)
    if kind == "buyer":
        exists = await ddl_commands_service().buyer_exists(org.attio_id, _vertical(row))
        return RowMatch(org.attio_id, exists)
    # One active seller role per organization, whatever the sector.
    with_roles = await resolve_organization(org.attio_id)
    has_role = with_roles is not None and any(r.is_active for r in with_roles.seller_roles)
    return RowMatch(org.attio_id, has_role)


async def _commit_row(
    kind: UploadKind, row: PlannedRow, requested_by: str | None, invoked_via: InvokedVia
) -> RowOutcome:
    async with write_lock:
        try:
            match = await match_row(kind, row)
            if match.exists:
                return RowOutcome(row=row.index, kind="skipped", reason="already in the CRM")
            await add_row(kind, row, match, requested_by, invoked_via)
        except (BuyerAlreadyExistsError, SellerAlreadyExistsError):
            return RowOutcome(row=row.index, kind="skipped", reason="already in the CRM")
        except PartialWriteError as exc:
            saved = "; ".join(exc.landed) or "nothing"
            reason = f"{describe_error(exc.cause)}; already saved: {saved}"
            return RowOutcome(row=row.index, kind="failed", reason=reason)
        except Exception as exc:
            logger.exception("bulk_upload_row_failed row=%d", row.index)
            return RowOutcome(row=row.index, kind="failed", reason=describe_error(exc))
    return RowOutcome(row=row.index, kind="added")


async def add_row(
    kind: UploadKind,
    row: PlannedRow,
    match: RowMatch,
    requested_by: str | None,
    invoked_via: InvokedVia,
) -> BuyerRole | SellerRole:
    is_new_org = match.org_attio_id is None
    # An existing organization is left as it is: our data wins.
    org_extracted: UploadRow = {**row.org_extracted, "domains": [row.domain]} if is_new_org else {}
    if kind == "buyer":
        return await write_buyer_add(
            is_new_org=is_new_org,
            org_attio_id=match.org_attio_id,
            org_name=row.org_name,
            org_extracted=org_extracted,
            role_extracted=row.role_extracted,
            requested_by=requested_by,
            invoked_via=invoked_via,
        )
    return await write_seller_add(
        is_new_org=is_new_org,
        org_attio_id=match.org_attio_id,
        org_name=row.org_name,
        org_extracted=org_extracted,
        role_extracted=row.role_extracted,
        requested_by=requested_by,
        invoked_via=invoked_via,
    )
