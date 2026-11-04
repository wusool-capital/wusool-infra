# Frontend guidance

Rules for any change under `client/`, the React web app served at `/app`.
[`client/README.md`](../client/README.md) covers the stack and commands, and
[`client/DESIGN.md`](../client/DESIGN.md) the design tokens.

## Design skills

Use both skills on every visible change: a new screen, a component, a layout
or a state such as loading, empty or error.

| Skill | When | What it gives you |
| --- | --- | --- |
| `design-taste-frontend` (taste skill) | Before you design or restyle anything | Art direction and house rules. The web app is an app screen, so follow its `references/app-screens.md` run. |
| `web-design-guidelines` | Before you finish, on the files you changed | A review against Vercel's Web Interface Guidelines: accessibility, focus, forms, motion, dark mode. |

If a skill isn't installed, install it before you start:

```bash
npx skills add Leonxlnx/taste-skill --skill design-taste-frontend
npx skills add vercel-labs/agent-skills --skill web-design-guidelines
```

Keep to the existing design tokens and components (`src/components/ui`,
shadcn). Add a shadcn component with `npx shadcn add <name>` rather than
writing one by hand.

## API access: Kubb only

The API client is generated. Never write a `fetch` call, a response type or a
query hook by hand.

- **Hooks.** Read and write through the TanStack Query hooks in
  `src/gen/hooks`, for example `useGetMatchRun` and `useStartDiscovery`. Use
  their query-key helpers (`getMatchRunQueryKey`) for cache updates.
- **Types.** Import request and response types from `src/gen/types`.
- **Validation.** Responses are parsed with the Zod schemas in `src/gen/zod`
  inside `src/lib/api-client.ts`. Validate any other untrusted data, such as
  storage or URL state, with Zod as well.
- **When the API changes.** Regenerate in the same change:

  ```bash
  cd server && uv run python scripts/export_openapi.py ../client/openapi.json
  cd ../client && npm run gen:api
  ```

  Commit `openapi.json` and `src/gen/`. `./checks.sh api` fails when they're
  stale.

## Tests

Every change ships with tests (Vitest and Testing Library):

- **Components.** Render with `renderWithQuery` (`src/test/render.tsx`) and
  build data from `src/test/fixtures.ts`. Stub `fetch` with
  `vi.stubGlobal("fetch", ...)` and return generated response shapes, so a
  test fails if the API contract drifts.
- **What to cover.** The behaviour a person sees: each state (loading, empty,
  error, success), what a click does, and what the user reads. Query by role
  and accessible name, not by class or test ID.
- **Logic.** Put parsing and formatting in plain `.ts` modules with their own
  unit tests, as `narrative.ts` and `export-fields.ts` do.

## Before you open a PR

Run the client checks from `client/`:

```bash
./checks.sh quality   # types, lint, formatting
./checks.sh unit      # tests
./checks.sh api       # generated client matches the server
./checks.sh build
```

For a visible change, also look at it in a browser at desktop and phone
widths, and update the GitBook pages that describe it.
