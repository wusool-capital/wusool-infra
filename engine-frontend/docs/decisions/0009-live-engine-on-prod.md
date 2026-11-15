# 0009: The live Engine on its own hostname

Date: 15 Nov 2026 · Status: accepted · Builds on: 0007, 0008

## Context
engine-dev reads the dev Toolkit. Advisors need the Engine on the production Toolkit, where their Attio members and the real CRM are.

## Decision
- A second copy at `engine.wusoolcapital.com`: Worker `wusool-engine-prod`, a second Access application in the same stack, and the same Access policy, so one change to who may sign in covers both. The older `wusool-engine` Worker belongs to the advisors' team and stays untouched.
- `deploy-engine.yml` serves both: a push to `dev` deploys engine-dev, a push to `prod` deploys the live Engine with `wrangler deploy --env production`. Each has its own GitHub environment and a repository variable that keeps the job off until its Access application exists.
- The deploy role trusts two separate pairs: `engine-dev` with `dev`, and `engine-prod` with `prod`.
- The live Worker proxies to the production Toolkit, which needs `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_ENGINE_AUD` (the live application's audience) in its own secret.

## Consequences
- Edits in the live Engine write the real Attio workspace and the production database.
- The live Engine only works once the Toolkit code is on `prod`, so `prod` is promoted from `dev` first.
- The Access applications are still applied by hand; the stack gains a second application and output (`access_aud_prod`).
