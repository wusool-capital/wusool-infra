# crm

Buyer and seller roles for the Engine frontend: reads with server-side filters, search
and cursor paging, and writes sent through `ddl_commands` (Attio first, then Postgres).
The `engine` module composes these reads into page payloads.

It reads the existing tables (`buyer_roles`, `seller_roles`, `organizations`, `person`,
`users`). When the Phase 0 tables land, only `persistence/` changes.

## Endpoints (`/api/v1`)

| Method and path | Engine function |
| --- | --- |
| `GET /me` | `getCurrentUser` |
| `GET`, `POST /buyer-roles` | `listBuyerRoles`, `addBuyer` |
| `GET`, `PATCH /buyer-roles/{id}` | `getBuyerRole`, `updateBuyer` |
| `GET`, `POST /seller-roles` | `listSellerRoles`, `addSeller` |
| `GET`, `PATCH /seller-roles/{id}` | `getSellerRole`, `updateSeller` |

- **Sign-in.** Every route needs the `Cf-Access-Jwt-Assertion` token Cloudflare Access adds.
  `auth` verifies it; the token's email must match an active `users` row. 401 for a bad
  token, 403 for an unknown email, 503 while `CF_ACCESS_TEAM_DOMAIN` and
  `CF_ACCESS_ENGINE_AUD` are unset.
- **Lists.** Filters are the Engine's own URL params (`sector`, `geography`, `checkSize`,
  `minEbitda`, `revenue`, `ebitda`, `openToSelling`, `q`), plus `cursor` and `limit` (at
  most 100). Rows are ordered by company name then id. `matched` counts rows under the
  filters and search, `total` counts every live row. These, the filter options and the team list come with the
  first page only; later pages hold rows and their contacts.
- **Edits.** `PATCH` needs `If-Match` with the row's `etag` (428 without, 412 when stale).
  The `etag` is the role's `updated_at`. Only the fields sent change. A value
  can be emptied by sending null, which empties it in Attio and Postgres. Checklists backed by a
  required column (`sector_focus`, geography) and a seller's `openToSelling` can change but not
  be emptied, and are refused with 422. The check and the write are not atomic, so two saves at the same
  moment can both pass. An Attio webhook that echoes a save back also moves
  `updated_at`, so a later edit can get a 412 until the row is reloaded.
- **Add.** `POST /buyer-roles` and `POST /seller-roles` are 201 with `Location` and `ETag`. They use
  the same Attio-first path as Slack's `/add-buyer` and `/add-seller`. A company that already
  holds the role (a buyer role for the sector, or any seller role) is refused with 409
  `buyer_exists` or `seller_exists`. The HQ is one of Attio's countries.
- **Errors.** RFC 9457 problem details with a stable `code`. A write that saved in Attio
  but failed in Postgres is 502 `partial_write`, with `landed` naming what saved; retrying
  the same edit finishes it.
- **Attribution.** Writes run as `invoked_via = "engine"`, attributed to the signed-in
  person's Attio user.

## More fields

Besides the fixed controls, every field the Slack add and edit forms take is available as a
generic `details` list (`key` and `value`): a select's option, a checklist, an amount, a date,
yes or no, a number, a percent, or text. The first page of each list carries the catalog
(`options.fields`: key, label, kind, options and whether the field is on the role or the
company), built from `ddl_commands.columns_for`. The Engine draws each field by its kind. A single
`GET /buyer-roles/{id}` or `/seller-roles/{id}` returns the current values (`details`), read with
`ddl_commands.get_record`; lists do not. The write goes through `edit_one` / `add_one`, which
checks each value against the field's options and type. Keys outside the catalog are refused.

## Fields with no source yet

These are null (the Engine shows "—") and cannot be edited:

- Buyer `type`, "Do not contact", sectors beyond the single `target_vertical`, and owner.
- Seller owner, notes, sector edits and geography edits.

A buyer with no check size or no EBITDA floor recorded never matches a filter on it. A buyer
with only one check-size bound counts as open-ended on the other side.

A buyer's or seller's HQ country is editable (`hq`). A seller's open to selling is saved as the exact
Attio `appetite_signal` (`appetiteSignal`); `openToSelling` only groups those for lists and filters.

A buyer's geography is editable. The Engine shows one list, and the Toolkit sorts the picks
into Attio's `target_region` and `target_country`. A group that already has values must keep
at least one, because a multi-select backed by a required column cannot be emptied.

Buyer `status` is the Attio `mandate_status`. Seller `openToSelling` maps the Attio
`appetite_signal`: "No Signal" is Unknown, the two inbound signals are Interested, and
"Warm Introduction / Direct Outreach" is Warm intro.

A seller's sector is the role's own `sector`, or the company's `sector_focus` when the role has
none, which is most roles. The sector column, filter, options and search all use that same value.

The two sectors stay apart in the drawer and the edit form. Each row also carries `companySector`
(the company's `sector_focus`, shown at the top) and, for a seller, `ownSector` (the role's own).
A buyer's role-level sector is its target vertical (`sectors`). The role-level one is shown under
Buyer or Seller details, read only.

## Layout

`domain/` (frozen dataclasses and errors), `application/` (the service and the reader and
writer ports), `persistence/` (the Postgres reader and its row mappers), `providers/` (the `ddl_commands`
writer), `api/` (schemas, problems, sign-in dependency, router).

## Dependencies

`auth` and `ddl_commands` (root exports only), `utilities`.
