# Buyers components

`routes/buyers-universe.tsx` lists every Attio buyer role (PRD U1) at `/buyers/universe?sector=...&buyer=<id>&panel=add|edit`.
`routes/buyers-search.tsx` finds new buyers (PRD S1, S2) at `/search/buyers?sector=...&q=...&searched=1` (one Search page with Sellers; old `/buyers/search` links redirect). Filter logic lives in `lib/buyer-filters.ts`.

| File | Notes |
| --- | --- |
| `buyer-filters.tsx` | Sector, geography, size, type and ticket selects, shared by both pages |
| `buyer-drawer.tsx` | Read-only record drawer; Add to a deal and Edit profile replace its content |
| `buyer-status-pill.tsx` | Active, Dormant, Do not contact |

Demo data lives in `demo/buyers-data.ts` and `demo/buyers-search-data.ts`.
