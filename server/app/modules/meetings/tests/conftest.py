"""Test fixtures.

Dummy env vars are set at import time (before any test module calls
`app.modules.meetings.config.get_settings()`, which requires
`DESKTOP_API_KEY` with no default) so collection never needs a real
.env, matching `ddl_commands/tests/conftest.py`.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("DESKTOP_API_KEY", "test-desktop-api-key")
# `build_note_writer()` now always constructs an `AttioNoteWriter`, which
# builds the Attio client eagerly and so needs a key.
os.environ.setdefault("ATTIO_API_KEY", "test-attio-key")
os.environ.setdefault("ATTIO_IS_TEST", "false")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.persistence.database import get_engine, import_all_models

import_all_models()


@pytest.fixture
async def db_session():
    """Yields a session bound to a transaction that's rolled back at
    teardown, so the existing dataset is never mutated. Skips the test
    outright if the database isn't reachable. Mirrors `matching_engine`'s
    own `db_session` fixture.

    `join_transaction_mode="create_savepoint"` makes this compatible with
    `NotesRepository.create`'s own `begin_nested()` -- savepoints nest, so
    that inner savepoint sits inside this fixture's outer one without
    conflict.
    """
    engine = get_engine()
    try:
        conn = await engine.connect()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    trans = await conn.begin()
    session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
