# Wusool Engine frontend

## What it does

The Wusool Engine is the advisors' internal app. The Buyers and Sellers pages
read and write live Toolkit data. Every other tab is still a clickable prototype
on invented demo data. It lives in the `engine-frontend/` folder and is served
from Cloudflare Workers at **engine-dev.wusoolcapital.com**.

## How it is hosted

1. The app is a single-page React app. `npm run build` writes static files to
   `engine-frontend/build/client`, and the Worker `wusool-engine-dev` serves them. Any
   path that is not a file returns `index.html`, so reloads and deep links work.
2. Cloudflare Access sits in front of the hostname. A visitor enters an
   `@wusoolcapital.com` address, Access emails a one-time code, and the
   sign-in lasts 24 hours. Other addresses get no code.
3. A small Worker script serves the app and forwards `/api/v1/*` to the Toolkit
   from the server side. The browser only talks to the Engine hostname, so there
   is no CORS and no cross-site cookie. The Worker's `TOOLKIT_ORIGIN` variable
   in `wrangler.jsonc` names the Toolkit.
4. The custom hostname is the only public address. The `workers.dev` address
   and Worker preview URLs are switched off in `engine-frontend/wrangler.jsonc`,
   because Access does not cover them.

## Sign-in and the API

* Access adds a signed token, `Cf-Access-Jwt-Assertion`, to every request it
  admits. The Toolkit checks the token's signature, audience and expiry against
  the Access team's public keys. It never trusts the email header alone, so
  calling the Toolkit directly gets a 401.
* The token's email must match an active row in `users`. An unknown email gets a
  403. There are no roles yet: every active team member can use the Engine.
* The Toolkit needs two settings in its Secrets Manager secret:
  `CF_ACCESS_TEAM_DOMAIN` (for example `wusoolcapital.cloudflareaccess.com`) and
  `CF_ACCESS_ENGINE_AUD` (the `access_aud` output of the `engine-frontend`
  stack). Until both are set, `/api/v1` answers 503.
* `crm` serves `/api/v1/buyer-roles`, `/api/v1/seller-roles` and `/api/v1/me`.
  `engine` serves the page payloads, `/api/v1/views/buyers` and
  `/api/v1/views/sellers`. Filters, search and order run on the Toolkit. Pages hold
  up to 100 rows, and the "Show more" button loads the next page.
* An edit needs the row's `ETag` in `If-Match`. If someone else changed the row,
  the Toolkit refuses it with 412. The check is not atomic with the write, and an
  Attio webhook echo can also change the version. Errors use the RFC 9457 problem
  format.
* Counts, filter options and the team list come with the first page of a list.
  "Show more" pages carry rows only.
* A write goes to Attio first, then Postgres, and is recorded in `command_runs`
  as `engine`. If Attio saves but Postgres fails, the Engine shows what saved and
  the edit can be retried.
* A removed person can keep an Access session for up to 24 hours.

## How it deploys

* **Pull requests** into `dev` or `prod` that touch `engine-frontend/` or the
  Toolkit's Engine modules run `Engine quality (required)`. It runs typecheck, a
  check that the generated API client matches the Toolkit's OpenAPI spec, and build.
* **Merging to `dev`** runs `deploy-engine.yml` with `VITE_DATA=live`: checks,
  build, `wrangler deploy`, then a check that the hostname and `/api/v1/me`
  both answer with an Access sign-in redirect. The run fails if either does not.
  Local work and tests use `VITE_DATA=demo`, the default.
* The Cloudflare deploy token is in AWS Secrets Manager. The job reads it
  through a GitHub OIDC role that only `deploy-engine.yml` on `dev` can assume.
  GitHub holds no Cloudflare secret.
* The deploy job stays off until the repository variable
  `ENGINE_ACCESS_APPLIED` is `true`.

## Access stack

The `engine-frontend` OpenTofu stack owns the Access application and its
policy. It is applied by hand, with a Cloudflare API token that can edit Access
applications and policies, before the first deploy. See
[Deployment and rollback](../operations-and-handover/deployment-and-rollback.md).

## Limits

* Only the Buyers and Sellers pages are live. Everything else is invented demo
  data.
* In live mode, Add to deal, New sell-side lead and the owner approach are
  greyed out until mandates and outreach are connected.
* Some fields have no source column yet and show as not set: a buyer's type and
  owner, and a seller's owner and notes. Their edit fields are locked. A buyer's
  sectors and geographies, and a seller's sector and geography, are read only.
  A new buyer takes its sector from the form.
* One hostname and one environment. There is no production copy.
