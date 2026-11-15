# Home components

One file per Home section, named after the PRD requirement it covers. `routes/home.tsx` loads the data and places the sections in the two cells of the grid: Your day, and Actions (Emails, Approvals, Workstreams) (`home-cell.tsx`).

| File | PRD | Notes |
| --- | --- | --- |
| `pending-review.tsx`, `pending-drawer.tsx` | H2 | Approve, Edit (drawer), Reject; codename check on email drafts |
| `action-emails.tsx`, `email-drawer.tsx` | H3 | Reply drawer with AI draft, Send, Not actionable |
| `workstreams.tsx` | H4 | Status chip menu, inline next step and due date edits |
| `agenda.tsx` | H7 | Meetings with prep cards, deadlines |
| `home-cell.tsx` | | One grid cell: title, tabs with counts, a body that scrolls |
| `morning-brief.tsx`, `tool-tab-check.tsx` | H10 | Brief (AI draft) and the end of day question |
| `home-context.tsx` | | `useHomeAction`, which posts an intent to the Home route action (toast lives in `ui/toast.tsx`) |

Sections and tabs marked `home__desktop-only` are hidden on phone.
