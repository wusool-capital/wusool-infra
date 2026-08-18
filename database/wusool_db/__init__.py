"""`wusool_db` — the single source of truth for every SQLAlchemy model mapping
onto the `wusool_crm` Postgres database.

Both `matching-engine` and `ddl-commands` (see `workflows/wusool-toolkit/`)
consume this package as a path dependency (`[tool.uv.sources]`, not a uv
workspace member — this package is a sibling of `workflows/`, one level
above that workspace's root) and import every ORM model from here rather
than owning any model file themselves.

This package intentionally has no engine/session/settings wiring of its
own — that stays app-specific (each app has its own `DATABASE_URL`/config).
This package only owns `Base` and the model classes registered onto it.
"""
