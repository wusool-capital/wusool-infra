"""Split database access into a runtime role and a migration (admin) role.

Everything that runs the app, and everyone who can read the toolkit secret,
connects as `wusool_app`: data access only, no DDL, no `TRUNCATE`. Schema
changes run as the RDS master (`wusool_admin`, owner of every table), whose
password is read live from the RDS-managed secret rather than copied into the
toolkit secret, so a password rotation cannot strand migrations.

`python -m app.modules.utilities.db_roles` runs after `alembic upgrade head`
in every deploy. It is idempotent: it creates or updates `wusool_app` and
re-applies the grants, so new tables are covered without a manual step.

The role's password has one source of truth. In steady state it is the one
already in the secret's `database_url`. To roll out or rotate, stage a new one
as `app_db_password` first, so no restart can read a URL whose role has no
password: this module sets the role and proves a login, then you point
`database_url` at it and delete `app_db_password`. With neither a staged
password nor a `wusool_app` URL, this module does nothing.
"""

import asyncio
import logging
import re
from functools import lru_cache

import asyncpg
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.engine import URL, make_url

from app.modules.utilities.secrets_manager import (
    SecretLoadError,
    SecretLocation,
    ToolkitSecret,
    fetch_toolkit_secret,
)

APP_ROLE = "wusool_app"

logger = logging.getLogger(__name__)

# Role names are interpolated into DDL, which cannot take bind parameters.
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class MasterSecret(BaseModel):
    """Shape of an RDS-managed master secret: credentials only, no host."""

    model_config = ConfigDict(frozen=True, extra="ignore", hide_input_in_errors=True)

    username: str
    password: str


@lru_cache
def fetch_master_secret(secret_arn: str, region: str) -> MasterSecret:
    """Read the RDS-managed master credentials; never cached beyond the process."""
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_arn)
        return MasterSecret.model_validate_json(response["SecretString"])
    except (BotoCoreError, ClientError, ValueError, KeyError) as exc:
        raise SecretLoadError(
            f"Cannot load the database master secret in {region} ({type(exc).__name__}). "
            "Check that the instance role may read it."
        ) from exc


def admin_database_url(database_url: str, master: MasterSecret) -> str:
    """Keep host, port and database from the app URL; swap in the master login."""
    admin = make_url(database_url).set(username=master.username, password=master.password)
    return admin.render_as_string(hide_password=False)


def resolve_app_password(toolkit: ToolkitSecret) -> str:
    """A staged password wins (rollout, rotation); else reuse the one in the URL."""
    if toolkit.app_db_password:
        return toolkit.app_db_password
    if toolkit.database_url:
        url = make_url(toolkit.database_url)
        if url.username == APP_ROLE and url.password:
            return url.password
    return ""


def _require_identifier(name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


async def provision_app_role(conn: asyncpg.Connection, role: str, password: str) -> None:
    """Create or update `role` with data-only access to every public table."""
    role = _require_identifier(role)
    async with conn.transaction():
        await conn.execute(
            f"""
            DO $do$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role} LOGIN;
              END IF;
            END $do$
            """
        )
        # The password travels as a bind parameter, never inside statement text,
        # so a failing statement cannot leak it into the server's error log.
        await conn.fetchval("SELECT set_config('app.role_password', $1, true)", password)
        await conn.execute(
            f"""
            DO $do$ BEGIN
              EXECUTE format(
                'ALTER ROLE %I WITH LOGIN PASSWORD %L',
                '{role}', current_setting('app.role_password')
              );
            END $do$
            """
        )
        database = await conn.fetchval("SELECT quote_ident(current_database())")
        # A restored database may still let PUBLIC create objects, which would
        # hand every role DDL on the public schema.
        await conn.execute(
            f"""
            REVOKE CREATE ON SCHEMA public FROM PUBLIC;
            GRANT CONNECT ON DATABASE {database} TO {role};
            GRANT USAGE ON SCHEMA public TO {role};
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role};
            """
        )
        # Migration state is the deploy pipeline's, not the app's, to change.
        if await conn.fetchval("SELECT to_regclass('public.alembic_version') IS NOT NULL"):
            await conn.execute(
                f"REVOKE INSERT, UPDATE, DELETE ON TABLE public.alembic_version FROM {role}"
            )
        if await conn.fetchval("SELECT has_schema_privilege($1, 'public', 'CREATE')", role):
            raise RuntimeError(f"{role} can still create objects in schema public")


async def verify_app_role(
    *, host: str | None, port: int | None, database: str | None, role: str, password: str
) -> None:
    """Prove the staged password works and the role cannot change the schema."""
    conn = await asyncpg.connect(
        host=host, port=port or 5432, user=role, password=password, database=database
    )
    try:
        await conn.fetchval("SELECT 1")
        try:
            await conn.execute("CREATE TABLE public.db_roles_probe (id int)")
        except asyncpg.InsufficientPrivilegeError:
            return
        await conn.execute("DROP TABLE public.db_roles_probe")
        raise RuntimeError(f"{role} was able to create a table")
    finally:
        await conn.close()


async def _provision(target: URL, master: MasterSecret, password: str) -> None:
    admin = await asyncpg.connect(
        host=target.host,
        port=target.port or 5432,
        user=master.username,
        password=master.password,
        database=target.database,
    )
    try:
        await provision_app_role(admin, APP_ROLE, password)
    finally:
        await admin.close()
    await verify_app_role(
        host=target.host,
        port=target.port,
        database=target.database,
        role=APP_ROLE,
        password=password,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    location = SecretLocation()
    secret_id = location.aws_secrets_manager_secret_id
    if not secret_id:
        raise SystemExit("AWS_SECRETS_MANAGER_SECRET_ID is empty; nothing to provision from")
    toolkit = fetch_toolkit_secret(secret_id, location.aws_region)
    password = resolve_app_password(toolkit)
    if not password:
        logger.warning(
            "no staged app_db_password and database_url is not the %s login; skipping", APP_ROLE
        )
        return
    if not location.db_master_secret_arn:
        raise SystemExit("DB_MASTER_SECRET_ARN is required to provision database roles")
    if not toolkit.database_url:
        raise SystemExit("The toolkit secret has no database_url to take the host from")
    master = fetch_master_secret(location.db_master_secret_arn, location.aws_region)
    asyncio.run(_provision(make_url(toolkit.database_url), master, password))
    logger.info("%s provisioned and login verified", APP_ROLE)


if __name__ == "__main__":
    main()
