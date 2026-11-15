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
| `GET /seller-roles`, `GET`, `PATCH /seller-roles/{id}` | `listSellerRoles`, `getSellerRole`, `updateSeller` |

- **Sign-in.** Every route needs the `Cf-Access-Jwt-Assertion` token Cloudflare Access adds.
  `auth` verifies it; the token's email must match an active `users` row. 401 for a bad
  token, 403 for an unknown email, 503 while `CF_ACCESS_TEAM_DOMAIN` and
  `CF_ACCESS_ENGINE_AUD` are unset.
- **Lists.** Filters are the Engine's own URL params (`sector`, `geography`, `checkSize`,
  `minEbitda`, `revenue`, `ebitda`, `openToSelling`, `q`), plus `cursor` and `limit` (at
  most 100). Rows are ordered by company name then id. `matched` counts rows under the
  filters and search, `total` counts every live row.
- **Edits.** `PATCH` needs `If-Match` with the row's `etag` (428 without, 412 when stale).
  The `etag` is the role's `updated_at`. Only the fields sent change; a field sent as null
  is cleared. The check and the write are not atomic.
- **Add.** `POST /buyer-roles` is 201 with `Location` and `ETag`. A company that already
  holds a buyer role for the sector is refused with 409 `buyer_exists`.
- **Errors.** RFC 9457 problem details with a stable `code`. A write that saved in Attio
  but failed in Postgres is 502 `partial_write`, with `landed` naming what saved; retrying
  the same edit finishes it.
- **Attribution.** Writes run as `invoked_via = "engine"`, attributed to the signed-in
  person's Attio user.

## Fields with no source yet

These are null (the Engine shows "—") and cannot be edited:

- Buyer `type`, "Do not contact", sectors beyond the single `target_vertical`, and owner.
- Seller owner, notes, sector edits and geography edits.

Buyer `status` is the Attio `mandate_status`. Seller `openToSelling` maps the Attio
`appetite_signal`: "No Signal" is Unknown, the two inbound signals are Interested, and
"Warm Introduction / Direct Outreach" is Warm intro.

## Layout

`domain/` (frozen dataclasses and errors), `application/` (the service and the reader and
writer ports), `persistence/` (the Postgres reader and its row mappers), `providers/` (the `ddl_commands`
writer), `api/` (schemas, problems, sign-in dependency, router).

## Dependencies

`auth` and `ddl_commands` (root exports only), `utilities`.
