# Database roles: data-only app login, admin-only DDL

> Internal execution detail retained outside the client-facing GitBook
> navigation.

Before this split, the toolkit secret's `database_url` held the RDS master
(`wusool_admin`). Anyone who could read the dev secret could run DDL, `DROP`
or `TRUNCATE` against the shared dev database. Now:

| Login | Used by | Can do |
| --- | --- | --- |
| `wusool_app` | the app, the nightly resync, every developer reading the dev secret | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on public tables. No DDL, no `TRUNCATE`, read-only on `alembic_version`. |
| `wusool_admin` (RDS master) | the deploy migration step, and admins running tunnel scripts | Everything. Owns every table. |

The master password lives only in the RDS-managed secret
(`rds!db-…`, ARNs in `infrastructure/terraform/envs/*.tfvars`). The deploy
migration step reads it live through the instance role, so a rotation cannot
strand migrations. The toolkit secret no longer needs a copy of it.

## How a deploy works

`_deploy.yml` runs one container on the instance:
`alembic upgrade head && python -m app.modules.utilities.db_roles`, with
`DB_MASTER_SECRET_ARN` set. Alembic connects as the master. Then `db_roles`
creates or updates `wusool_app` from `app_db_password` in the toolkit secret,
re-applies the grants, and logs in as `wusool_app` to prove the password works
and `CREATE TABLE` is denied. New tables are covered on the same deploy.

Without `app_db_password` in the secret, `db_roles` does nothing, so deploying
the code changes nothing until you stage the password.

A laptop has no `DB_MASTER_SECRET_ARN`, so `alembic` falls back to the app
login and a stray `alembic upgrade head` fails with a permission error.

## Rollout, per environment (dev first)

Do these in order. Staging the password before switching `database_url` means
no restart can read a login that doesn't exist yet.

1. **Deploy the code.** Merge and let the deploy run. Migrations now run as the
   master from the RDS secret; the app still uses `database_url` as before.
2. **Stage the password.** Add a top-level `app_db_password` key to
   `/wusool/<env>/toolkit`. Use hex so the URL needs no escaping:

   ```bash
   umask 077
   PW=$(openssl rand -hex 24)
   aws secretsmanager get-secret-value --secret-id /wusool/dev/toolkit \
     --query SecretString --output text \
     | jq --arg p "$PW" '.app_db_password=$p' > /tmp/toolkit-secret.json
   aws secretsmanager put-secret-value --secret-id /wusool/dev/toolkit \
     --secret-string file:///tmp/toolkit-secret.json
   rm -f /tmp/toolkit-secret.json
   ```

3. **Create the role.** Open an SSM session on the toolkit instance and run the
   provisioning step by hand, with the ARN from `tofu output db_master_secret_arn`
   in `stacks/toolkit`:

   ```bash
   sudo docker run --rm --env-file /opt/toolkit/toolkit/runtime.env \
     -e 'DB_MASTER_SECRET_ARN=<arn>' \
     "$(sudo docker inspect --format '{{.Config.Image}}' toolkit-toolkit-1)" \
     python -m app.modules.utilities.db_roles
   ```

   Expect `wusool_app provisioned and login verified`. Any error leaves
   `database_url` untouched.
4. **Switch the app over.** Set `database_url` in the same secret to
   `postgresql://wusool_app:<PW>@<same host>:5432/wusool_crm`, then
   `sudo docker restart toolkit-toolkit-1` and check `/health`. Confirm the app's
   login with a one-off `docker exec` that selects `current_user`; expect
   `wusool_app`, and a `CREATE TABLE` from it must be denied. The nightly resync
   refuses to run on dev (`ATTIO_IS_TEST=true`), so check it on prod only: run
   the nightly workflow once after the prod switch.
5. **Roll back if needed.** Restore the previous `database_url` (Secrets Manager
   keeps `AWSPREVIOUS`) and restart. The master is never changed.

Rotate the app password the same way: stage a new `app_db_password`, run step 3
(it updates the role), then update `database_url` and restart. Existing
connections keep working; new ones fail until the restart, so do it in one go.

## Who needs the master now

`rds!db-*` secrets are denied to the `Developers` and `PowerUsers` IAM groups
and the `WusoolDeveloper` role (`stacks/account/access.tf`). Admins
(`WusoolAdmin`) run anything that needs DDL or `TRUNCATE`:
`server/scripts/postgres-sync/truncate-dev.ps1`, the other postgres-sync
scripts, and tunnel work in `rds-tunnel-runbook.md`. Developers can still open
a tunnel and connect as `wusool_app`.

## Limits

This protects against laptop mistakes and app bugs, not a determined attacker.
The toolkit container shares the instance role, so code execution inside it can
read the master secret. `PowerUserAccess` can also run SSM commands on the
instance. Real separation needs a separate role for migrations and a separate
prod account.
