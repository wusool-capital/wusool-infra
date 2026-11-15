# 0002: Demo data and actions

Date: 7 Nov 2026 · Status: accepted

## Context
The prototype must feel real (approve, send, edit) without live integrations. Later each read and write goes to the Toolkit API.

## Decision
- `app/demo/types.ts` mirrors the tools of record. `app/demo/data.ts` holds invented records. `app/demo/api.ts` is the only module routes import; each function stands in for one Toolkit endpoint.
- Routes read with `clientLoader` and write with `clientAction` (intents posted without navigation). This is React Router's own data flow, so going live replaces function bodies, not components.
- Demo writes change an in-memory copy and reset on reload. Sends show "Demo: nothing was sent."
- "Now" is fixed at Wed 11 Nov 2026 08:40 Dubai so overdue items and scorecard pace look the same on every visit. All dates render in Dubai time.
- Drawers live in the URL (`?email=`, `?review=`) so Slack deep links (PRD H11) can open the exact item.
- Rules in code, never AI: scorecard pace status (`lib/scorecard.ts`), 24-hour reply overdue, codename check (`lib/codename.ts`).

## Consequences
- Tasks are labelled as Engine tasks (PRD decisions table), not Attio tasks.
- Mandate rows on Home do not link yet; they link to the Deal view once Mandates is built.
