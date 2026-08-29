# Prod Postgres sync

No separate scripts here on purpose. Every script in
[`../dev-postgres-sync`](../dev-postgres-sync) is already environment-agnostic
— none of them hardcode dev — they act entirely on whatever `DATABASE_URL`
(and `SOURCE_ATTIO_API_KEY`/`DEV_ATTIO_API_KEY`) is in the environment when
you run them, exactly like Alembic itself. A duplicate `prod` copy would just
be the same logic maintained twice, drifting apart over time.

To run any of them against prod, supply a prod `DATABASE_URL` first. See
`../dev-postgres-sync/rds-tunnel-runbook.md` for the tunnel steps — same
mechanism for prod, pointed at `wusool-prod-postgres` / the prod n8n instance
/ `eu-central-1` instead of dev's.
