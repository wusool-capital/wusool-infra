# Deal view components

`routes/deal-view.tsx` is one deal at `/deals/<dealId>?tab=...&panel=...` and handles every action.

| File | PRD | Notes |
| --- | --- | --- |
| `deal-overview.tsx` | MV1, MV2, MV4 | Header with Edit and Email client, figures, stage bars; the compact bar shown once the overview scrolls away |
| `buyers-tab.tsx` | MB1 to MB3 | Counterparty table; "Targets" on buy-side deals |
| `counterparty-drawer.tsx` | MB4, MB5 | Status, contacts, Apollo enrichment with credit cost, outreach with the link chosen by NDA status, history |
| `action-drawers.tsx` | MB2, MV1, MV3, MH3 | Find more, Send CIM, Email client, Log decision |
| `materials-tab.tsx`, `materials-drawers.tsx`, `materials.ts` | MM1 to MM5 | Client documents, deliverables with the Claude prompt, agreements with fee terms behind Show terms |
| `offers-tab.tsx`, `offer-drawers.tsx` | MO1 to MO3 | Offers table, side-by-side comparison, add by hand or from an attachment, accept or reject with a reason |
| `history-tab.tsx` | MH1 to MH3 | Pinned next step, filters, events with source, decisions marked |
| `deal-panel.tsx`, `use-deal.ts` | | The one open drawer, named in the URL; the route action hook |
| `status-pill.tsx` | | Counterparty status pills from DESIGN.md |

Demo data lives in `demo/mandates-data.ts`.
