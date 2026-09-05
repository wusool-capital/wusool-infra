# organizations

Organization persistence — the one canonical implementation of trigram
organization-name search, shared by `ddl_commands` (Slack org-selection/
search/edit) and `matching_engine` (buyer/seller org-name search), where
this same query used to be duplicated independently in both. No `domain/`
layer, no `api/`, no `bootstrap.py` — every consumer already works with the
ORM `Organization` row directly (mirrors `ddl_commands`'s own precedent: no
business-logic-needing entity exists for Organization today).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
organizations/
  __init__.py                                   # __all__: OrganizationRepository, OrganizationRepositoryPort
  application/ports/organizations.py            # OrganizationRepositoryPort Protocol
  persistence/repositories/organizations_repository.py
```

## Public contract

`OrganizationRepositoryPort`: `get_by_id`, `get_by_id_with_roles`,
`search_by_name` (the shared trigram query, `ix_organizations_name_trgm`),
`create`, `update` — all return `app.models.Organization` or `None` — plus
`lock`, which returns nothing.

`lock(attio_id)` takes a `SELECT ... FOR UPDATE` row lock on the
organization for the rest of the caller's transaction. It exists because
`ddl_commands`' `/add-buyer`//add-seller` create paths check "does this org
already have an active role" in application code — the 2026-08-28 migration
(`b8f4c1e93a56`) moved `UNIQUE` off `org_attio_id` on the role tables, so
nothing in the DB rejects a second active row. Serializing on the parent
org row is what closes that window; see
`ddl_commands/README.md`, "Known limitation: concurrent writes to the same
organization". The lock belongs here rather than in `ddl_commands` because
`organizations` owns the table — a cross-module reach into this module's
`persistence/` would be a boundary violation.

Consumers import only `from app.modules.organizations import
OrganizationRepository, OrganizationRepositoryPort` (the `__all__`).
`ddl_commands/bootstrap.py` constructs the concrete repository per-session;
`ddl_commands`'s own Unit-of-Work also exposes an `organizations` slot
backed by it, since buyer/seller writes touch both a role repository and
this one in the same transaction.

## Testing

No integration tests of its own — exercised indirectly through
`ddl_commands`'s buyer/seller use-case tests. `tests/test_architecture.py`
enforces this module's own `application/` never imports `persistence/`/
`fastapi`/`pydantic`/`sqlalchemy` directly.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
