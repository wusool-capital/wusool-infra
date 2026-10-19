"""Describe and render exceptions without leaking row data into logs.

A database error's message quotes data: SQLAlchemy appends the bound
parameters, and Postgres adds `DETAIL: Failing row contains (...)` or
`Key (email)=(...) already exists`. Both can carry PII, so database errors are
reduced to their type, SQLSTATE and constraint name. Duck-typed on `orig` (how
SQLAlchemy wraps a driver error) so this stays free of any SQL library.
"""

import logging
import traceback
from types import TracebackType

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]

_MAX_CHAIN = 10


def is_database_error(exc: BaseException) -> bool:
    return getattr(exc, "orig", None) is not None


def describe_error(exc: BaseException) -> str:
    """The exception type, plus SQLSTATE and constraint/table names for a database
    error. Never the message."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return type(exc).__name__
    driver_error = getattr(orig, "__cause__", None) or orig
    parts = [type(exc).__name__, type(driver_error).__name__]
    for label, attr in (
        ("sqlstate", "sqlstate"),
        ("constraint", "constraint_name"),
        ("table", "table_name"),
    ):
        value = getattr(driver_error, attr, None) or getattr(orig, attr, None)
        if value:
            parts.append(f"{label}={value}")
    return " ".join(parts)


def _chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain and len(chain) < _MAX_CHAIN:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def format_exception_safely(exc_info: ExcInfo) -> str:
    """A traceback as `logging` would print it, except that when a database error
    is anywhere in the exception chain every message is dropped: a wrapper such as
    `PartialWriteError(str(cause))` repeats the database message."""
    chain = _chain(exc_info[1])
    if not any(is_database_error(e) for e in chain):
        return logging.Formatter().formatException(exc_info)
    lines = ["Traceback (most recent call last):\n", *traceback.format_tb(exc_info[2])]
    for exc in chain:
        text = describe_error(exc) if is_database_error(exc) else "<message omitted>"
        lines.append(f"{type(exc).__name__}: {text}\n")
    return "".join(lines).rstrip("\n")
