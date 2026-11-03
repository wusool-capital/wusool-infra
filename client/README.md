# Wusool web app

The browser front end for the Wusool Toolkit. Today it runs `/find-match` as
one sequential page (buyer, profile check, matching, shortlist, discovery,
export); the other tools are listed as coming soon. The bot container serves
the build at `/app`, and the app calls the same origin's `/api/*` routes
(see `server/app/modules/matching_engine/README.md`, "Web app").

## Run it

```bash
# Backend, from server/ (after `aws sso login`):
export WEB_API_KEY=local-dev-key
docker compose up

# Front end, from client/:
npm ci
npm run dev        # http://localhost:5173/app, proxies /api to localhost:8000
```

`docker compose` publishes the bot on port 8080 by default, so either set
`COMPOSE_BOT_PORT=8000` or change the proxy target in `vite.config.ts`. The
app asks for the access key (`WEB_API_KEY`) once per browser tab.

`VITE_API_BASE_URL` (see `.env.example`) stays empty for same-origin hosting;
set it only when the app is hosted apart from the API.

## Checks

`./checks.sh [all|quality|unit|api|build]` runs the same gates as the
`Client quality` workflow (`.github/workflows/client-quality.yml`, a required
check):

| Target | Runs |
| --- | --- |
| `quality` | `tsc` (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), ESLint (`typescript-eslint` strict type-checked, `no-explicit-any` as an error), Prettier |
| `unit` | Vitest and Testing Library |
| `api` | Regenerates the API client and fails if `openapi.json` or `src/gen/` changed |
| `build` | `vite build` |

## The API client

The client is generated, never written by hand:

1. `server/scripts/export_openapi.py` writes `client/openapi.json` from the
   web router alone, with no server or database.
2. `npm run gen:api` runs Kubb (`kubb.config.ts`) and writes TypeScript types,
   Zod schemas, client functions and TanStack Query hooks to `src/gen/`.

Every response is parsed with its Zod schema in `src/lib/api-client.ts`
before a component sees it; a mismatch shows an error instead of partial
data. That module also adds the access key and drops it on a 401.

Generated files start with `// @ts-nocheck`: Kubb's output isn't written for
`exactOptionalPropertyTypes`. Our own code stays fully strict, and every call
site is still checked against the generated types.

Commit `openapi.json` and `src/gen/` whenever a route or schema changes.

## Design system

`DESIGN.md` (Linear's design system plus an "App extensions" section) is the
source of truth. Its tokens are copied one-to-one into
`src/styles/tokens.css`, mapped to Tailwind utilities in the `@theme` block
of `src/styles/index.css`, and onto shadcn's variable names there too, so
components never hold a hex value. Tailwind's own colour palette and shadows
are cleared.

The shadcn components in `src/components/ui/` are restyled to the DESIGN.md
component specs. `cn()` in `src/lib/utils.ts` registers the custom type scale
with `tailwind-merge`; without it, `text-caption` is read as a colour and
dropped.

Each screen goes through the loop in `frontend-plan.md` §1.3: set its
direction (the taste skill), build with tokens only, take screenshots at 1440,
1024, 768 and 480px with Playwright, fix what they show, then audit with the
web-design-guidelines rules.

## Structure

```
src/
  routes/          file-based routes (TanStack Router); _app.tsx is the shell
    _app/          index (tools), find-match, runs/$runId, settings
  features/
    find-match/    one component per step, the steps bar and run state
  components/      shell (Sidebar, TopBar, ApiKeyGate) and ui/ (shadcn)
  lib/             api-client, access key, recent runs, formatting
  gen/             generated API client (do not edit)
```

Recent runs in the sidebar are remembered per device in `localStorage`; there
is no list-runs endpoint yet.
