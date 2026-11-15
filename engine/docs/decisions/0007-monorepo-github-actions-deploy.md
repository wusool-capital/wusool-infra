# 0007: Deploy from the monorepo with GitHub Actions

Date: 15 Nov 2026 · Status: accepted · Supersedes: 0006

## Context
The Engine moved into the `engine/` folder of the wusool-infra monorepo. The first deployment (Workers Builds from the old repo, Worker `wusool-engine`) belongs to the advisors' team and is left untouched. Its Access policy covered only the workers.dev address, so Worker preview URLs served the app without a login.

## Decision
- A separate Worker, `wusool-engine-dev`, at `engine-dev.wusoolcapital.com`.
- `wrangler.jsonc` sets `workers_dev: false` and `preview_urls: false`, so the custom hostname is the only public address.
- `infrastructure/terraform/stacks/engine-frontend` owns the Cloudflare Access application and policy: email one-time PIN, `@wusoolcapital.com` only, 24h session. The same model as the old setup.
- `.github/workflows/deploy-engine.yml` builds and runs `wrangler deploy` on every merge to `dev` that touches `engine/`. `engine-quality.yml` runs typecheck and build on pull requests.

## Consequences
- Apply the Access stack before the first deploy. The deploy job stays off until the repository variable `ENGINE_ACCESS_APPLIED` is `true`.
- The deploy token lives in the GitHub environment `engine-dev`. The Access token is used locally only.
- The old Worker and its Workers Builds trigger keep running until the advisors' team retires them.
