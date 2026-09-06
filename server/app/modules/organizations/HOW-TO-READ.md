# How to read `organizations`

A walkthrough for someone who has never seen this module before. This is a
tiny module (~145 lines across two files) — you'll finish reading the code
faster than this file, but here's what to look for.

## The one-sentence version

One Postgres repository for the `organizations` table, used by both
`ddl_commands` (Slack org search/edit/create) and `matching_engine`
(buyer/seller org-name search), so the same trigram-search query isn't
duplicated in two places.

## Why there's no `domain/` layer

You'll notice this module skips straight from `application/ports/` to
`persistence/` — no framework-free domain entity in between. That's
deliberate, not an oversight: both consumers immediately read ORM
attributes off `Organization` (including its eager-loaded
`seller_roles`/`buyer_roles`), so there's no business logic anywhere that
actually needs a framework-free representation. If you're tempted to add
one "for consistency" with `matching_engine`'s domain layer, don't — add
it only when a real use case needs it.

## The six methods, and the one that isn't obvious

`persistence/repositories/organizations_repository.py` is the whole
module's logic. Five of its six methods do exactly what they say
(`get_by_id`, `search_by_name`, `create`, `update`,
`get_by_id_with_roles`). The sixth, `lock`, is worth understanding before
you touch anything that calls it:

**`lock(attio_id)` takes a `SELECT ... FOR UPDATE` row lock on an
organization for the rest of the caller's transaction.** It exists to
close a real race: `ddl_commands`' `/add-buyer`/`/add-seller` need to
check "does this org already have an active role" before inserting one,
but nothing in the database rejects two concurrent submissions from both
passing that check before either commits (a migration removed the
`UNIQUE` constraint that used to catch this). Holding this lock across
the check-then-insert is what actually serializes two people running
`/add-buyer` for the same org at the same moment. This method lives here
— not in `ddl_commands`, which is the only thing that calls it — because
this module owns the `organizations` table; a cross-module reach into
someone else's `persistence/` would be exactly the layering violation the
`domain must not import SQLAlchemy` rule (and its sibling rule for
`persistence/`) exists to prevent.

`README.md`'s "Public contract" section has the full story and points at
`ddl_commands/README.md`'s own writeup of the concurrency bug this closes
— read that if you need the complete picture, don't re-derive it from the
code.

## The other file: `OrganizationFields`

`application/ports/organizations.py` is almost entirely one `TypedDict`,
`OrganizationFields` — every column `create`/`update` can set, deliberately
excluding `attio_id`/`name` (always required positional args) and the
server-managed timestamps. If you're adding a new writable column to
`organizations`, this is the one place to add it; the repository's
`create`/`update` signatures (`**fields: Unpack[OrganizationFields]`) pick
it up automatically.

## Where to go next

- Adding a new writable column → `OrganizationFields` in
  `application/ports/organizations.py`.
- The concurrent-write race `lock()` closes → `README.md`'s "Public
  contract" section, plus `ddl_commands/README.md`'s "Known limitation".
- Everything else is a straightforward CRUD method — just read the
  repository file directly, it's short.
