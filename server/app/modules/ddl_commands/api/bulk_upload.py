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

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.ddl_commands.api.bulk_columns import routes_for
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
from app.modules.ddl_commands.api.schemas import PrefillValue
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
_write_lock = asyncio.Lock()


class BulkUploadError(Exception):
    pass


class InvalidUploadError(BulkUploadError):
    pass


class PreviewNotFoundError(BulkUploadError):
    pass


class RowProblem(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: int  # 1-based position in the list, or the spreadsheet line for a file
    message: str


class PreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_id: uuid.UUID
    new: int
    existing: int
    invalid: int
    existing_rows: tuple[int, ...]
    problems: tuple[RowProblem, ...]


class RejectedUpload(BaseModel):
    """A strict preview found invalid rows: nothing was stored, so there is no
    preview id and nothing to commit."""

    model_config = ConfigDict(frozen=True)

    invalid: int
    problems: tuple[RowProblem, ...]


@dataclass(frozen=True)
class _Match:
    org_attio_id: str | None
    exists: bool


@dataclass(frozen=True)
class _Checked:
    valid: tuple[PlannedRow, ...]
    problems: tuple[RowProblem, ...]
    invalid: int


async def preview_buyers(rows: Sequence[UploadRow]) -> PreviewResult:
    return await _finish("buyer", _validate("buyer", rows, None), "mcp")


async def preview_sellers(rows: Sequence[UploadRow]) -> PreviewResult:
    return await _finish("seller", _validate("seller", rows, None), "mcp")


async def preview_buyers_strict(
    rows: Sequence[UploadRow], *, row_numbers: Sequence[int], invoked_via: InvokedVia
) -> PreviewResult | RejectedUpload:
    """All or nothing, for a file a person uploaded: any invalid row rejects the
    whole upload. `row_numbers` are the spreadsheet lines to report."""
    return await _strict("buyer", rows, row_numbers, invoked_via)


async def preview_sellers_strict(
    rows: Sequence[UploadRow], *, row_numbers: Sequence[int], invoked_via: InvokedVia
) -> PreviewResult | RejectedUpload:
    return await _strict("seller", rows, row_numbers, invoked_via)


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
    started = CommitProgress(state="running", total=len(preview.rows))
    _store.set_progress(preview_id, started)
    get_shared_task_runner().run(
        lambda: run_commit(preview, requested_by, on_done), name=f"bulk-upload-{preview_id}"
    )
    return started


async def run_commit(
    preview: StoredPreview, requested_by: str | None, on_done: OnDone | None = None
) -> None:
    progress = CommitProgress(state="running", total=len(preview.rows))
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
        parsed = _parse(kind, number, raw)
        if isinstance(parsed, list):
            invalid += 1
            problems.extend(RowProblem(row=number, message=m) for m in parsed)
            continue
        key = (parsed.domain, _vertical(parsed) if kind == "buyer" else None)
        if key in seen:
            invalid += 1
            problems.append(RowProblem(row=number, message=f"duplicate of row {seen[key]}"))
            continue
        seen[key] = number
        valid.append(parsed)
    return _Checked(tuple(valid), tuple(problems), invalid)


async def _finish(kind: UploadKind, checked: _Checked, invoked_via: InvokedVia) -> PreviewResult:
    """Splits the valid rows into new and already in the CRM, and stores the new ones."""
    planned: list[PlannedRow] = []
    existing_rows: list[int] = []
    for row in checked.valid:
        # shortcut: one lookup per row (indexed), fine at the 1,000-row cap; batch if it grows.
        if (await _match(kind, row)).exists:
            existing_rows.append(row.index)
        else:
            planned.append(row)

    preview = StoredPreview(
        id=uuid.uuid4(), kind=kind, rows=tuple(planned), invoked_via=invoked_via
    )
    _store.save(preview)
    return PreviewResult(
        preview_id=preview.id,
        new=len(planned),
        existing=len(existing_rows),
        invalid=checked.invalid,
        existing_rows=tuple(existing_rows),
        problems=checked.problems,
    )


async def _strict(
    kind: UploadKind,
    rows: Sequence[UploadRow],
    row_numbers: Sequence[int],
    invoked_via: InvokedVia,
) -> PreviewResult | RejectedUpload:
    checked = _validate(kind, rows, row_numbers)
    if checked.invalid:
        # Before any database lookup: the upload is already rejected.
        return RejectedUpload(invalid=checked.invalid, problems=checked.problems)
    return await _finish(kind, checked, invoked_via)


def _parse(kind: UploadKind, index: int, raw: UploadRow) -> PlannedRow | list[str]:
    routes = routes_for(kind)
    fields = {key: route.spec for key, route in routes.items()}
    problems: list[str] = []

    org_name = raw.get("org_name")
    if not isinstance(org_name, str) or not org_name.strip():
        problems.append("org_name is required")
    host = _host(raw.get("domain"))
    if host is None:
        problems.append("domain is required (a company website or domain)")
    if kind == "buyer" and not raw.get("target_vertical"):
        problems.append("target_vertical is required")
    problems.extend(
        f"unknown field '{k}'" for k in sorted(raw) if k not in fields and k not in _ROW_KEYS
    )

    given = {k: v for k, v in raw.items() if k in fields and v is not None}
    normalized = normalize_prefill(given, fields, warn_on_drop=False)
    # A silently dropped value, or a trimmed list, would be lost data, so say so.
    problems.extend(
        f"value not allowed for '{k}'"
        for k, v in given.items()
        if k not in normalized or (isinstance(v, list) and normalized[k] != v)
    )
    org_extracted: UploadRow = {
        routes[k].name: v for k, v in normalized.items() if routes[k].target == "org"
    }
    role_extracted: UploadRow = {
        routes[k].name: v for k, v in normalized.items() if routes[k].target == "role"
    }
    try:
        OrganizationUpdate.model_validate(org_extracted)
        (BuyerUpdate if kind == "buyer" else SellerUpdate).model_validate(role_extracted)
    except ValidationError as exc:
        # Location and type only: the message can quote the row's values.
        problems.extend(
            f"invalid '{'.'.join(str(p) for p in e['loc'])}' ({e['type']})" for e in exc.errors()
        )

    if problems or not isinstance(org_name, str) or host is None:
        return problems
    return PlannedRow(
        index=index,
        org_name=org_name.strip(),
        domain=host,
        org_extracted=org_extracted,
        role_extracted=role_extracted,
    )


def _host(value: PrefillValue | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    host = company_hostname(url if "//" in url else f"https://{url}")
    return host.lower().removeprefix("www.") if host else None


def _vertical(row: PlannedRow) -> str | None:
    vertical = row.role_extracted.get("target_vertical")
    return vertical if isinstance(vertical, str) else None


async def _match(kind: UploadKind, row: PlannedRow) -> _Match:
    org = await find_organization_by_domains([row.domain, f"www.{row.domain}"])
    if org is None:
        return _Match(None, False)
    if kind == "buyer":
        exists = await ddl_commands_service().buyer_exists(org.attio_id, _vertical(row))
        return _Match(org.attio_id, exists)
    # One active seller role per organization, whatever the sector.
    with_roles = await resolve_organization(org.attio_id)
    has_role = with_roles is not None and any(r.is_active for r in with_roles.seller_roles)
    return _Match(org.attio_id, has_role)


async def _commit_row(
    kind: UploadKind, row: PlannedRow, requested_by: str | None, invoked_via: InvokedVia
) -> RowOutcome:
    async with _write_lock:
        try:
            match = await _match(kind, row)
            if match.exists:
                return RowOutcome(row=row.index, kind="skipped", reason="already in the CRM")
            await _add(kind, row, match, requested_by, invoked_via)
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


async def _add(
    kind: UploadKind,
    row: PlannedRow,
    match: _Match,
    requested_by: str | None,
    invoked_via: InvokedVia,
) -> None:
    is_new_org = match.org_attio_id is None
    # An existing organization is left as it is: our data wins.
    org_extracted: UploadRow = {**row.org_extracted, "domains": [row.domain]} if is_new_org else {}
    if kind == "buyer":
        await write_buyer_add(
            is_new_org=is_new_org,
            org_attio_id=match.org_attio_id,
            org_name=row.org_name,
            org_extracted=org_extracted,
            role_extracted=row.role_extracted,
            requested_by=requested_by,
            invoked_via=invoked_via,
        )
    else:
        await write_seller_add(
            is_new_org=is_new_org,
            org_attio_id=match.org_attio_id,
            org_name=row.org_name,
            org_extracted=org_extracted,
            role_extracted=row.role_extracted,
            requested_by=requested_by,
            invoked_via=invoked_via,
        )
