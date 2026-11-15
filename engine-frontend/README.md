# Wusool Engine

Internal operating system for Wusool Capital advisors. This is the clickable prototype on a demo account with invented data.

- What to build: `docs/PRD.md`
- How it looks: `docs/DESIGN.md`
- Rules for contributors and Claude Code: `CLAUDE.md`
- Decisions: `docs/decisions/`

## Run

```bash
npm install
npm run dev
```

Checks before a pull request: `./checks.sh` (typecheck and build), then click through at 1440px and 390px wide.

## Deploy (Cloudflare)

Every merge to `dev` that touches `engine-frontend/` deploys to Cloudflare Workers through `.github/workflows/deploy-engine.yml` (decision 0007). Config: `wrangler.jsonc`. Address: `engine-dev.wusoolcapital.com`, behind Cloudflare Access (email one-time PIN, `@wusoolcapital.com` only), managed in `infrastructure/terraform/stacks/engine-frontend`.

Local check of the production setup: `npm run build`, then `npx wrangler dev`.

## Working on the repo

- Branch from `dev`, one branch per tab, open a pull request into `dev`. The `Engine quality (required)` check runs typecheck and build.
- Run `./checks.sh` before a pull request, then click through at 1440px and 390px wide.

## Layout

- `app/root.tsx`: page shell (left nav, toast, phone notice)
- `app/demo/`: invented data and `api.ts`, the only module routes read and write through
- `app/routes/`: one file per built tab; `placeholder.tsx` for tabs not built yet
- `app/routes.ts`: route table, one entry per tab
- `app/lib/nav.ts`: the 13 tabs in 5 groups, used by the nav and the placeholders
- `app/components/shell/`: shell components
- `app/styles.css`: tokens and component styles from DESIGN.md
