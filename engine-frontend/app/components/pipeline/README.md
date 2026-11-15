# Pipeline components

`routes/pipeline.tsx` loads the deals and handles the actions. Filters (view, owner, status) and the open deal live in the URL.

| File | PRD | Notes |
| --- | --- | --- |
| `pipeline-toolbar.tsx` | P1 | Board or list, owner (default me), status |
| `kanban-board.tsx` | P1 | One column per stage; drag a card to change its stage |
| `deal-table.tsx` | P1 | Brand table with sortable headers; Enter opens a row |
| `deal-drawer.tsx` | P2, P3 | Quick view: key fields, contacts, business blurb with codename check |
| `engagement-panel.tsx` | P4, P5 | Terms with skill defaults, fee examples, documents, email, Send |

Terms, defaults and fee maths live in `lib/engagement.ts`; see `docs/decisions/0003-engagement-letter-terms.md`.
