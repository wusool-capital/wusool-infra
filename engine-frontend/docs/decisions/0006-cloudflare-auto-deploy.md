# 0006: Host on Cloudflare Workers, deployed from GitHub

Date: 7 Nov 2026 · Status: superseded by 0007

## Context
The prototype is a single-page app with no server: `npm run build` writes static files to `build/client`. CLAUDE.md fixes Cloudflare Workers (static assets) behind Cloudflare Access. Jules chose automatic deploys from GitHub over deploying from a laptop.

## Decision
- `wrangler.jsonc` serves `build/client` as static assets, with `not_found_handling: "single-page-application"` so deep links such as `/deals/d-falcon` return the app instead of a 404.
- Workers Builds is connected to `wusool-capital/wusool-engine`: every push to `main` runs `npm run build`, then `npx wrangler deploy`. Pull request branches get preview builds.
- Wrangler is a pinned dev dependency (4.155.0), so the Cloudflare build uses the same version as local checks.
- Cloudflare Access (Google sign-in, @wusoolcapital.com only) protects the Worker's address before it is shared.

## Consequences
- Merging to `main` is the deploy. A broken build stops the deploy; the last good version stays live.
- The compatibility date must not be newer than the pinned Wrangler supports; bump both together.
- `npx wrangler dev` previews the production setup locally (`cloudflare-preview` in `.claude/launch.json`).
