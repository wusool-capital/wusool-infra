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
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.ddl_commands.api.bulk_store import (
    MAX_ROWS,
    CommitProgress,
    InMemoryPreviewStore,
    PlannedRow,
    PreviewStore,
    RowOutcome,
    StoredPreview,
    UploadKind,
)
from app.modules.ddl_commands.api.buyer_write import write_buyer_add
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME, BuyerUpdate
from app.modules.ddl_commands.api.dependencies import (
    ddl_commands_service,
    find_organization_by_domains,
    resolve_organization,
)
from app.modules.ddl_commands.api.organizations import (
    ORGANIZATION_FIELDS_BY_NAME,
    OrganizationUpdate,
)
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.seller_write import write_seller_add
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME, SellerUpdate
from app.modules.ddl_commands.api.slack.views.dynamic_fields import normalize_prefill
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.buyers import BuyerAlreadyExistsError
from app.modules.ddl_commands.application.sellers import SellerAlreadyExistsError
from app.modules.discovery.domain.drafts import company_hostname
from app.modules.utilities import get_shared_task_runner
from app.modules.utilities.domain.safe_errors import describe_error

logger = logging.getLogger(__name__)

UploadRow = dict[str, PrefillValue | None]

# `domains` is set from the single `domain` column, so it is not accepted as a field.
_ORG_FIELDS = {n: s for n, s in ORGANIZATION_FIELDS_BY_NAME.items() if n != "domains"}
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

    row: int  # 1-based position in the uploaded list
    message: str


class PreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_id: uuid.UUID
    new: int
    existing: int
    invalid: int
    existing_rows: tuple[int, ...]
    problems: tuple[RowProblem, ...]


@dataclass(frozen=True)
class _Match:
    org_attio_id: str | None
    exists: bool


async def preview_buyers(rows: Sequence[UploadRow]) -> PreviewResult:
    return await _preview("buyer", rows)


async def preview_sellers(rows: Sequence[UploadRow]) -> PreviewResult:
    return await _preview("seller", rows)


def status(preview_id: uuid.UUID) -> CommitProgress:
    progress = _store.progress(preview_id)
    if progress is None:
        raise PreviewNotFoundError(str(preview_id))
    return progress


def commit(preview_id: uuid.UUID, *, requested_by: str | None) -> CommitProgress:
    """Starts the add in the background and returns at once; poll `status`.
    A commit already running is not started twice. After it finishes, calling
    again re-checks every row, so only rows still missing are added.
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
        lambda: run_commit(preview, requested_by), name=f"bulk-upload-{preview_id}"
    )
    return started


async def run_commit(preview: StoredPreview, requested_by: str | None) -> None:
    progress = CommitProgress(state="running", total=len(preview.rows))
    try:
        for row in preview.rows:
            progress = progress.record(await _commit_row(preview.kind, row, requested_by))
            _store.set_progress(preview.id, progress)
    except BaseException:
        # Cancelled mid-batch (shutdown): mark it so a new commit may resume.
        _store.set_progress(preview.id, progress.model_copy(update={"state": "interrupted"}))
        raise
    _store.set_progress(preview.id, progress.model_copy(update={"state": "done"}))


async def _preview(kind: UploadKind, rows: Sequence[UploadRow]) -> PreviewResult:
    if not 1 <= len(rows) <= MAX_ROWS:
        raise InvalidUploadError(f"send between 1 and {MAX_ROWS} rows, got {len(rows)}")

    planned: list[PlannedRow] = []
    existing_rows: list[int] = []
    problems: list[RowProblem] = []
    invalid = 0
    seen: dict[tuple[str, str | None], int] = {}
    for index, raw in enumerate(rows, start=1):
        parsed = _parse(kind, index, raw)
        if isinstance(parsed, list):
            invalid += 1
            problems.extend(RowProblem(row=index, message=m) for m in parsed)
            continue
        key = (parsed.domain, _vertical(parsed) if kind == "buyer" else None)
        if key in seen:
            invalid += 1
            problems.append(RowProblem(row=index, message=f"duplicate of row {seen[key]}"))
            continue
        seen[key] = index
        # shortcut: one lookup per row (indexed), fine at the 1,000-row cap; batch if it grows.
        if (await _match(kind, parsed)).exists:
            existing_rows.append(index)
        else:
            planned.append(parsed)

    preview = StoredPreview(id=uuid.uuid4(), kind=kind, rows=tuple(planned))
    _store.save(preview)
    return PreviewResult(
        preview_id=preview.id,
        new=len(planned),
        existing=len(existing_rows),
        invalid=invalid,
        existing_rows=tuple(existing_rows),
        problems=tuple(problems),
    )


def _parse(kind: UploadKind, index: int, raw: UploadRow) -> PlannedRow | list[str]:
    role_fields = BUYER_ROLE_FIELDS_BY_NAME if kind == "buyer" else SELLER_ROLE_FIELDS_BY_NAME
    fields = {**_ORG_FIELDS, **role_fields}
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
    # A silently dropped value would be lost data, so say so.
    problems.extend(f"value not allowed for '{k}'" for k in given if k not in normalized)
    org_extracted: UploadRow = {n: v for n, v in normalized.items() if n in _ORG_FIELDS}
    role_extracted: UploadRow = {n: v for n, v in normalized.items() if n in role_fields}
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


async def _commit_row(kind: UploadKind, row: PlannedRow, requested_by: str | None) -> RowOutcome:
    async with _write_lock:
        try:
            match = await _match(kind, row)
            if match.exists:
                return RowOutcome(row=row.index, kind="skipped", reason="already in the CRM")
            await _add(kind, row, match, requested_by)
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


async def _add(kind: UploadKind, row: PlannedRow, match: _Match, requested_by: str | None) -> None:
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
            invoked_via="mcp",
        )
    else:
        await write_seller_add(
            is_new_org=is_new_org,
            org_attio_id=match.org_attio_id,
            org_name=row.org_name,
            org_extracted=org_extracted,
            role_extracted=row.role_extracted,
            requested_by=requested_by,
            invoked_via="mcp",
        )
