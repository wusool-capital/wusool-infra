"""A real Postgres violation quotes the row, and none of it may reach a log."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.utilities.domain.safe_errors import describe_error, format_exception_safely

SECRET = "jane.doe@example.com"


async def _violate_a_check(db_session: AsyncSession) -> DBAPIError:
    with pytest.raises(DBAPIError) as raised:
        await db_session.execute(
            text(
                "INSERT INTO activities(subject_type, subject_attio_id, event_type, actor_type) "
                "VALUES ('Person', :s, 'Not A Valid Type', 'system')"
            ),
            {"s": SECRET},
        )
    return raised.value


async def test_the_raw_error_really_does_quote_the_row(db_session: AsyncSession) -> None:
    """Guards the premise: without redaction the value is in the exception text."""
    error = await _violate_a_check(db_session)

    assert SECRET in str(error.orig.__cause__)


async def test_describe_error_names_the_constraint_not_the_row(db_session: AsyncSession) -> None:
    error = await _violate_a_check(db_session)

    description = describe_error(error)

    assert "activities_event_type_format" in description
    assert "23514" in description
    assert SECRET not in description


async def test_the_engine_hides_bound_parameters(db_session: AsyncSession) -> None:
    """Not enough alone: Postgres still quotes the row in its own message, which is
    why the log formatter redacts database errors too."""
    error = await _violate_a_check(db_session)

    assert "[parameters:" not in str(error)
    assert "hidden due to hide_parameters" in str(error)


async def test_a_logged_traceback_of_the_error_is_redacted(db_session: AsyncSession) -> None:
    error = await _violate_a_check(db_session)

    formatted = format_exception_safely((type(error), error, error.__traceback__))

    assert SECRET not in formatted
    assert "activities_event_type_format" in formatted
