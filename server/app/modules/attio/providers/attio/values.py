"""Extracts typed values out of Attio's `values`/`entry_values` attribute
shape. A direct port of the helper functions embedded in
`database/sync-postgres.ps1` — same field-value shape, same rules — just
operating on one fetched record/entry instead of a paged-through list.
Generic to Attio's wire format, not specific to any one module's sync
business logic.
"""

from datetime import date as _date
from datetime import datetime as _datetime
from typing import Any

from app.modules.attio.domain.records import AttioRecord, AttioValueEntry
from app.modules.attio.providers.attio.money import MoneyJson

ValuesBySlug = dict[str, list[AttioValueEntry]]


def vals(record: AttioRecord) -> ValuesBySlug:
    return record.get("values") or record.get("entry_values") or {}


def raw_items(v: ValuesBySlug, slug: str) -> list[AttioValueEntry]:
    """The active (non-superseded) raw value entries for `slug` — for
    callers that need more than `first`/`titles`/etc. extract, e.g. a
    multi-valued field's `email_address` on each item."""
    return [x for x in (v.get(slug) or []) if x.get("active_until") is None]


def first(v: ValuesBySlug, slug: str) -> Any:
    """The return type is genuinely attribute-type-dependent (`str` for
    text/select/status/email/domain/date, `float`/`bool` for a number/
    checkbox field read through here directly) — callers already know which
    from the Attio attribute they're reading, and assign into a properly
    typed row-builder field (see `attio_sync_types.py`), which is where the
    real type safety lives for this value.
    """
    xs = raw_items(v, slug)
    if not xs:
        return None
    x = xs[0]
    for path in (
        ("value",),
        ("option", "title"),
        ("status", "title"),
        ("email_address",),
        ("domain",),
        ("timestamp",),
        ("date",),
    ):
        cur: Any = x
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is not None:
            return cur
    return None


def titles(v: ValuesBySlug, slug: str) -> list[str]:
    out: list[str] = []
    for x in raw_items(v, slug):
        option_title = (x.get("option") or {}).get("title")
        status_title = (x.get("status") or {}).get("title")
        value = option_title or status_title or x.get("value")
        if value is not None and str(value) not in out:
            out.append(str(value))
    return out


def ref(v: ValuesBySlug, slug: str) -> str | None:
    xs = raw_items(v, slug)
    return xs[0].get("target_record_id") if xs else None


def refs(v: ValuesBySlug, slug: str) -> list[str]:
    result: list[str] = []
    for x in raw_items(v, slug):
        target_record_id = x.get("target_record_id")
        if target_record_id:
            result.append(target_record_id)
    return result


def actor(v: ValuesBySlug, slug: str) -> str | None:
    xs = raw_items(v, slug)
    if not xs:
        return None
    return xs[0].get("referenced_actor_id") or xs[0].get("workspace_member_id")


def boolean(v: ValuesBySlug, slug: str) -> bool | None:
    value = first(v, slug)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "yes", "1", "checked")


def number(v: ValuesBySlug, slug: str) -> float | None:
    value = first(v, slug)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def integer(v: ValuesBySlug, slug: str) -> int | None:
    value = number(v, slug)
    return None if value is None else int(value)


def date(v: ValuesBySlug, slug: str) -> _date | None:
    """`first`'s raw `date`-type value is a plain `"YYYY-MM-DD"` string —
    asyncpg's binary protocol rejects a bare `str` for a `DATE` column
    (needs `datetime.date`), so every `date`-typed Postgres column must go
    through this, never `first` directly.
    """
    raw = first(v, slug)
    return _date.fromisoformat(raw) if raw else None


def timestamp(v: ValuesBySlug, slug: str) -> _datetime | None:
    """Same rule as `date`, for `timestamp`-type values feeding a
    `TIMESTAMP` column — asyncpg needs `datetime.datetime`, not `str`.
    """
    raw = first(v, slug)
    return _datetime.fromisoformat(raw) if raw else None


def money(v: ValuesBySlug, slug: str) -> MoneyJson | None:
    xs = raw_items(v, slug)
    if not xs:
        return None
    x = xs[0]
    amount = x.get("currency_value", x.get("value"))
    currency = x.get("currency_code", x.get("currency"))
    if amount in (None, ""):
        return None
    return {"amount": amount, "currency": currency}


def domains(v: ValuesBySlug) -> list[str]:
    value = first(v, "domains")
    if isinstance(value, list):
        return value
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def record_id(r: AttioRecord) -> str:
    return str((r.get("id") or {}).get("record_id") or r.get("record_id") or "")


def entry_id(r: AttioRecord) -> str:
    return str((r.get("id") or {}).get("entry_id") or r.get("entry_id") or "")


def parent_id(r: AttioRecord) -> str:
    value = r.get("parent_record_id")
    if isinstance(value, dict):
        return str(value.get("record_id") or "")
    return str(value or (r.get("id") or {}).get("record_id") or "")
