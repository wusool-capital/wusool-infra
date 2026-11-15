# Wusool Engine frontend

## What it does

The Wusool Engine is the advisors' internal app: a clickable prototype of every
tab, running on invented demo data. It lives in the `engine/` folder and is
served as static files from Cloudflare Workers at
**engine-dev.wusoolcapital.com**.

## How it is hosted

1. The app is a single-page React app. `npm run build` writes static files to
   `engine/build/client`, and the Worker `wusool-engine-dev` serves them. Any
   path that is not a file returns `index.html`, so reloads and deep links work.
2. Cloudflare Access sits in front of the hostname. A visitor enters an
   `@wusoolcapital.com` address, Access emails a one-time code, and the
   sign-in lasts 24 hours. Other addresses get no code.
3. The custom hostname is the only public address. The `workers.dev` address
   and Worker preview URLs are switched off in `engine/wrangler.jsonc`,
   because Access does not cover them.

## How it deploys

* **Pull requests** into `dev` or `prod` that touch `engine/` run
  `Engine quality (required)`: typecheck and build.
* **Merging to `dev`** runs `deploy-engine.yml`: build, `wrangler deploy`, then
  a check that the hostname answers with an Access sign-in redirect. The run
  fails if it does not.
* The deploy token and Cloudflare account ID are secrets of the GitHub
  environment `engine-dev`. The deploy job stays off until the repository
  variable `ENGINE_ACCESS_APPLIED` is `true`.

## Access stack

The `engine-frontend` OpenTofu stack owns the Access application and its
policy. It is applied by hand, with a Cloudflare API token that can edit Access
applications and policies, before the first deploy. See
[Deployment and rollback](../operations-and-handover/deployment-and-rollback.md).

## Limits

* The data is invented. Nothing connects to Attio or the Toolkit yet.
* One hostname and one environment. There is no production copy.
