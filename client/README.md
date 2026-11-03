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

| Target    | Runs                                                                                                                                                                |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality` | `tsc` (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), ESLint (`typescript-eslint` strict type-checked, `no-explicit-any` as an error), Prettier |
| `unit`    | Vitest and Testing Library                                                                                                                                          |
| `api`     | Regenerates the API client and fails if `openapi.json` or `src/gen/` changed                                                                                        |
| `build`   | `vite build`                                                                                                                                                        |

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

`src/styles/tokens.css` is the source of truth. It holds the Wusool Capital
palette taken from wusoolcapital.com: a near-black ground tinted toward its
midnight blue (`#000523`), gold-white ink (`#f7f5f0`), and gulf blue
(`#c6e1ee`) as the one accent. The tokens are mapped to Tailwind utilities in
the `@theme` block of `src/styles/index.css` and onto shadcn's variable names,
so components never hold a hex value. Tailwind's own colour palette and shadows
are cleared. `DESIGN.md` (Linear's design system) is kept for reference only.

The rules the components follow:

- **Type.** Instrument Sans for everything, with tabular figures on. Instrument
  Serif, after the firm's wordmark, is used for page titles only. Six sizes:
  `title`, `figure`, `section`, `lead`, `body`, `small`.
- **Accent.** Gulf blue marks the current selection as a 1px line (rail item,
  current step, selected row, focused field), the scores above the discovery
  line, and the screen's one primary action.
- **Surfaces.** Cards sit one step darker than the ground, with 1px borders
  and no shadows. Corners are square (2px controls, 4px panels), like the
  site's buttons.
- **Status.** Pills are a dark tint of the hue with the hue as text. Notices
  carry their colour only on the icon and a 2px leading edge.

The shadcn components in `src/components/ui/` are restyled to these rules.
`cn()` in `src/lib/utils.ts` registers the type scale with `tailwind-merge`;
without it, `text-small` is read as a colour and dropped.

## Structure

```
src/
  routes/          file-based routes (TanStack Router); _app.tsx is the shell
    _app/          index (home), find-match, runs/$runId, settings
  features/
    find-match/    buyer search, profile check, the run funnel, the shortlist
                   list and detail, discovery, and the steps bar
  components/      shell (Rail, PageHeader, Mark, ApiKeyGate) and ui/ (shadcn)
  lib/             api-client, access key, recent runs, formatting
  gen/             generated API client (do not edit)
```

Recent runs on the home page are remembered per device in `localStorage`;
there is no list-runs endpoint yet. Each row fetches its run to show how many
sellers are still to review.
