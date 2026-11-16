# Wusool Engine frontend

## What it does

The Wusool Engine is the advisors' internal app. The Buyers and Sellers pages
read and write live Toolkit data. Every other tab is still a clickable prototype
on invented demo data. It lives in the `engine-frontend/` folder and is served
from Cloudflare Workers.

There are two copies. **engine-dev.wusoolcapital.com** reads the dev Toolkit and
is for testing. **engine.wusoolcapital.com** is the live Engine, and it reads the
production Toolkit, so its edits change the real CRM.

## How it is hosted

1. The app is a single-page React app. `npm run build` writes static files to
   `engine-frontend/build/client`, and the Worker serves them: `wusool-engine-dev` for dev and `wusool-engine-prod` for
   the live Engine. Any
   path that is not a file returns `index.html`, so reloads and deep links work.
2. Cloudflare Access sits in front of the hostname. A visitor enters an
   `@wusoolcapital.com` or `@dopaminecap.com` address, Access emails a one-time
   code, and the sign-in lasts 24 hours. Other addresses get no code. The Toolkit
   then needs the same address on an active Attio member.
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
* `crm` serves `/api/v1/buyer-roles`, `/api/v1/seller-roles` and `/api/v1/me`. Adding a
  buyer or seller uses the same Attio-first write as Slack's `/add-buyer` and `/add-seller`.
  A duplicate domain is refused, and the HQ is picked from Attio's list of countries.
  `engine` serves the page payloads, `/api/v1/views/buyers` and
  `/api/v1/views/sellers`. Filters, search and order run on the Toolkit. Pages hold
  up to 100 rows, and the "Show more" button loads the next page.
* An edit needs the row's `ETag` in `If-Match`. If someone else changed the row,
  the Toolkit refuses it with 412. The check is not atomic with the write, and an
  Attio webhook echo can also change the version. Errors use the RFC 9457 problem
  format.
* The drawer and edit form show the company's sector at the top, and it is editable. The
  role's own, a buyer's target vertical or a seller role's sector, sits under Buyer or Seller
  details, read only. The Sellers list uses the role's sector, or the company's when it has none.
* The edit form covers every field Slack's edit commands change, including HQ country. Option
  lists come from Attio, and open to selling is the exact appetite signal.
* A web address in the drawer is a link that opens in a new tab, shortened to its domain.
* The record drawer shows the same extra fields as the Edit form, read only, and leaves out
  any field with no value. They load from the single-record read when the drawer opens.
* Range filters (check size, EBITDA, revenue) are a two-handle slider with named steps
  from Any to $1B+. The URL keeps the range in millions of dollars, such as `checkSize=0.2-5`.
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
* **Merging to `prod`** runs the same workflow for the live Engine, with
  `wrangler deploy --env production`, the `engine-prod` GitHub environment and the
  `engine.wusoolcapital.com` check.
* The Cloudflare deploy token is in AWS Secrets Manager. The job reads it
  through a GitHub OIDC role. The role only trusts `deploy-engine.yml` on `dev`
  with the `engine-dev` environment, or on `prod` with `engine-prod`. GitHub holds
  no Cloudflare secret.
* Each deploy job stays off until its repository variable is `true`:
  `ENGINE_ACCESS_APPLIED` for dev and `ENGINE_PROD_ACCESS_APPLIED` for the live Engine.

## Access stack

The `engine-frontend` OpenTofu stack owns both Access applications, the one
policy they share, and the deploy role. It is applied by hand, with a Cloudflare
API token that can edit Access applications and policies, before the first
deploy of each environment. See
[Deployment and rollback](../operations-and-handover/deployment-and-rollback.md).

## Limits

* Only the Buyers and Sellers pages are live. Everything else is invented demo
  data.
* In live mode, Add to deal, New sell-side lead and the owner approach are
  greyed out until mandates and outreach are connected.
* Some fields have no source column yet and show as not set: a buyer's type and
  owner, and a seller's owner and notes. Their edit fields are locked, as is a
  seller's geography.
* The edit and add forms also offer every other field the Slack commands take.
  Examples are a buyer's model, deal structure and EV ceiling, a seller's sell
  timeline and margins, and a company's description and funding. The Toolkit lists
  them, and the form draws each by its kind: a select, a checklist, an amount, a
  date, yes or no, or text. Emptying a field saves it as empty in Attio. A checklist
  backed by a required column, such as sector focus, can change but not be emptied.
  Nothing is saved until you press Save to Attio.
* A buyer's geography can be edited. The Toolkit sorts the picks into Attio's
  target region and target country fields. As in Slack, a group that has values
  must keep at least one.
