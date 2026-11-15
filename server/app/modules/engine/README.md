# engine

The page-read API behind the Engine frontend (`engine-frontend/`). Each endpoint
returns everything one page needs, composed from other modules' services. The module
owns no tables and no writes.

| Endpoint | Engine function | Source |
| --- | --- | --- |
| `GET /api/v1/views/buyers` | `getBuyersUniverse` | `crm` buyer roles |
| `GET /api/v1/views/sellers` | `getSellersUniverse` | `crm` seller roles |

Both take the page's own URL params (`sector`, `geography`, `checkSize`, `minEbitda`,
`revenue`, `ebitda`, `openToSelling`, `q`) plus `cursor` and `limit` (at most 100), and
return `matched` (rows under the filters), `total` (every live row), `nextCursor` and the
filter `options`.

`deals`, `counterparties` and `emails` are always empty for now, and `unavailable` names
the connectors behind them (`mandates` in phase 3, `outreach` in phase 4), so the page
loads with those blocks blank.

Sign-in and errors are `crm`'s: Cloudflare Access token in, RFC 9457 problem out.

## Dependencies

`crm` (its root exports only).
