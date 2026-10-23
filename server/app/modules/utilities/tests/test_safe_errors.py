import json
import logging
import sys

from app.modules.utilities.domain.logging import JsonFormatter
from app.modules.utilities.domain.safe_errors import (
    describe_error,
    format_exception_safely,
    is_database_error,
)

SECRET = "jane.doe@example.com"


class _DriverError(Exception):
    sqlstate = "23505"
    constraint_name = "person_email_key"
    table_name = "person"


class _WrappedDatabaseError(Exception):
    """Shaped like SQLAlchemy's DBAPIError: the driver error hangs off `orig`."""

    def __init__(self) -> None:
        driver = _DriverError(f"Key (email)=({SECRET}) already exists.")
        super().__init__(f"(IntegrityError) duplicate key [parameters: ('{SECRET}',)]")
        self.orig = driver
        self.orig.__cause__ = driver


def _raise_wrapped_twice() -> None:
    try:
        raise _WrappedDatabaseError()
    except _WrappedDatabaseError as exc:
        # Like `PartialWriteError(landed, exc)`: the wrapper repeats the message.
        raise RuntimeError(str(exc)) from exc


def test_a_plain_exception_is_described_by_its_type_only() -> None:
    assert describe_error(ValueError(SECRET)) == "ValueError"
    assert not is_database_error(ValueError(SECRET))


def test_a_database_error_is_described_without_its_message() -> None:
    text = describe_error(_WrappedDatabaseError())

    assert "sqlstate=23505" in text
    assert "constraint=person_email_key" in text
    assert "table=person" in text
    assert SECRET not in text


def test_a_traceback_without_a_database_error_is_unchanged() -> None:
    try:
        raise ValueError("plain failure")
    except ValueError:
        formatted = format_exception_safely(sys.exc_info())  # type: ignore[arg-type]

    assert "ValueError: plain failure" in formatted


def test_a_wrapped_database_error_drops_every_message_in_the_chain() -> None:
    try:
        _raise_wrapped_twice()
    except RuntimeError:
        formatted = format_exception_safely(sys.exc_info())  # type: ignore[arg-type]

    assert SECRET not in formatted
    assert "constraint=person_email_key" in formatted
    assert "Traceback" in formatted


def test_the_json_log_line_never_carries_the_database_message() -> None:
    logger = logging.getLogger("test_safe_errors.json")
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(JsonFormatter().format(record))

    logger.addHandler(_Capture())
    logger.propagate = False
    try:
        _raise_wrapped_twice()
    except RuntimeError:
        logger.exception("sync failed")

    (line,) = records
    assert SECRET not in line
    assert json.loads(line)["message"] == "sync failed"
    assert "person_email_key" in json.loads(line)["exception"]
