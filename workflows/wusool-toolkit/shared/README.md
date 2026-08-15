# shared

Scaffold only — intentionally empty. Once `../ddl-commands` exists and a
real cross-bot reuse need is known, extract the proven-generic pieces here.

Candidates identified in `../matching-engine/app/shared/` (domain-free,
zero coupling to buyers/sellers/matching): `errors/`, `logging/`,
`idempotency/`, `tasks/`, and the DB session/engine/health mechanism
(`database/base.py`, `database/session.py`, `database/health.py` — not
`database/models/`, `database/registry.py`, or `database/schema_check.py`,
which are matching-engine-specific).

Do not add code or move anything into this folder until a second bot
actually needs it — moving working, tested, DB-touching code for a
hypothetical consumer is not worth the risk before one exists.
