"""The runtime role can change data but never the schema.

Runs against the disposable CI database as a superuser, using a throwaway role
so the shared `wusool_app` is never touched.
"""

import os
import secrets
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.modules.utilities.db_roles import provision_app_role, verify_app_role

ROLE = "wusool_app_probe"


@pytest.fixture
async def admin() -> AsyncIterator[asyncpg.Connection]:
    url = make_url(os.environ["DATABASE_URL"])
    try:
        conn = await asyncpg.connect(
            host=url.host,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            database=url.database,
        )
    except (OSError, asyncpg.PostgresError):
        pytest.skip("no reachable Postgres for the role-split test")
    if not await conn.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
        await conn.close()
        pytest.skip("role-split test needs a superuser")
    try:
        yield conn
    finally:
        await conn.execute("DROP TABLE IF EXISTS public.role_probe")
        await conn.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {ROLE}"
        )
        await conn.execute(f"DROP OWNED BY {ROLE}")
        await conn.execute(f"DROP ROLE IF EXISTS {ROLE}")
        await conn.close()


async def test_app_role_has_data_access_but_no_ddl(admin: asyncpg.Connection) -> None:
    password = secrets.token_hex(16)
    url = make_url(os.environ["DATABASE_URL"])
    await admin.execute("CREATE TABLE public.role_probe (id int PRIMARY KEY, v text)")
    await provision_app_role(admin, ROLE, password)
    await verify_app_role(
        host=url.host, port=url.port, database=url.database, role=ROLE, password=password
    )

    app = await asyncpg.connect(
        host=url.host, port=url.port or 5432, user=ROLE, password=password, database=url.database
    )
    try:
        await app.execute("INSERT INTO public.role_probe VALUES (1, 'a')")
        await app.execute("UPDATE public.role_probe SET v = 'b' WHERE id = 1")
        assert await app.fetchval("SELECT v FROM public.role_probe WHERE id = 1") == "b"
        await app.execute("DELETE FROM public.role_probe WHERE id = 1")

        denied = [
            "CREATE TABLE public.nope (id int)",
            "ALTER TABLE public.role_probe ADD COLUMN z int",
            "DROP TABLE public.role_probe",
            "TRUNCATE public.role_probe",
            "UPDATE public.alembic_version SET version_num = 'x'",
            "DELETE FROM public.alembic_version",
        ]
        for statement in denied:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(statement)
    finally:
        await app.close()


async def test_provisioning_twice_changes_the_password(admin: asyncpg.Connection) -> None:
    url = make_url(os.environ["DATABASE_URL"])
    first, second = secrets.token_hex(16), secrets.token_hex(16)
    await provision_app_role(admin, ROLE, first)
    await provision_app_role(admin, ROLE, second)
    await verify_app_role(
        host=url.host, port=url.port, database=url.database, role=ROLE, password=second
    )
    with pytest.raises(asyncpg.InvalidPasswordError):
        await verify_app_role(
            host=url.host, port=url.port, database=url.database, role=ROLE, password=first
        )
