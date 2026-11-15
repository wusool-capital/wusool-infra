# Sellers components

`routes/sellers-universe.tsx` lists every Attio seller role (PRD U1) at `/sellers/universe?sector=...&seller=<id>&panel=approach|add|lead|edit`. `routes/sellers-search.tsx` finds new owners (PRD S1 to S3). Filter logic lives in `lib/seller-filters.ts`.

| File | Notes |
| --- | --- |
| `seller-drawer.tsx` | Read-only record drawer; each "..." action replaces its content: owner approach (PRD S3), add to a buy-side deal, new sell-side lead, edit profile |
| `ask-owners-drawer.tsx` | PRD S3 from Sellers search: one editable note per owner, one Send |
| `open-to-selling-pill.tsx` | Unknown, Interested, Warm intro |

Shared with Buyers: `ui/actions-menu.tsx`, `ui/filter-bar.tsx`, `ui/search-actions.tsx`, `pipeline/lead-drawer.tsx`. Demo data lives in `demo/sellers-data.ts` and `demo/sellers-search-data.ts`.
