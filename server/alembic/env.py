"""alembic/env.py

Alembic migration environment for wusool_crm — async SQLAlchemy 2, the same
proven pattern already used by wusool-scribe's own alembic/env.py against
this same database.

Scribe (a separate repo) has its own, completely independent Alembic chain
and its own standalone Postgres — NOT this database. Its migrations create
a `meetings` table too, but that's a different table in a different
database (scribe's own internal aggregate root) that happens to share a
name with `wusool_crm.meetings` (the simple "publish" table defined in
`database/sql/005_meetings.sql`, which scribe's publish job only ever
INSERTs/UPDATEs via the locked-down `scribe_pub` role — see that file's own
header comment and its `GRANT SELECT, INSERT, UPDATE` line, no DDL rights
at all). wusool-infra genuinely owns 100% of this database's DDL, so this
chain maps and tracks `meetings` like any other table here — no exclusion,
no special-casing. (An earlier draft of this file assumed the two chains
touched the same table and excluded it defensively; that assumption was
wrong, verified against scribe's actual SQL comments, and the exclusion
was removed.)
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.modules.utilities import fetch_toolkit_secret
from app.modules.utilities.secrets_manager import SecretLocation

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import Base AND all models so their tables register on metadata.
# `app.models` importing successfully is what makes every one of the
# 23 mapped tables visible to autogenerate — a model that never gets
# imported here is invisible to it and --autogenerate proposes dropping its
# table (see ALEMBIC_MIGRATION_HANDOVER.md point 2).
# ---------------------------------------------------------------------------
import app.models  # noqa: F401, E402
from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# DATABASE_URL → sqlalchemy.url
# ---------------------------------------------------------------------------
def _database_url() -> str:
    """Resolve the database URL for migrations.

    `DATABASE_URL` wins when set (CI, a local override). Otherwise the URL
    comes from the same Secrets Manager blob (`database_url`) the app reads,
    so no second credential exists; never hardcode one here. The secret is
    read live, so an RDS password rotation needs only the secret updated.

    Mirrors matching-engine/app/config.py's own normalization: force the
    asyncpg driver regardless of input scheme, and never append `sslmode`
    — asyncpg doesn't understand libpq's `sslmode` query parameter; adding
    it would likely break the connection outright.
    """
    url = os.environ.get("DATABASE_URL") or _secret_database_url()
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _secret_database_url() -> str:
    location = SecretLocation()
    if not location.aws_secrets_manager_secret_id:
        raise RuntimeError(
            "Set DATABASE_URL, or AWS_SECRETS_MANAGER_SECRET_ID to read it from Secrets Manager"
        )
    return fetch_toolkit_secret(
        location.aws_secrets_manager_secret_id, location.aws_region
    ).database_url


# `set_main_option` stores into a ConfigParser-backed section, which treats
# `%` as interpolation syntax (e.g. alembic.ini's own `%(here)s`) — a real
# RDS-generated password containing a literal `%` (common; verified against
# dev's actual master credential) raises `ValueError: invalid interpolation
# syntax` here otherwise. `%%` is ConfigParser's own escape for a literal
# `%`, and `get_main_option`/`get_section` (used below) unescape it back
# automatically — this round-trips correctly, it does not corrupt the URL.
config.set_main_option("sqlalchemy.url", _database_url().replace("%", "%%"))


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (async)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None  # set unconditionally above, via set_main_option
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
