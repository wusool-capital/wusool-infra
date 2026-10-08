# Deploying the lead-magnet tools

This module ships inside the existing toolkit container — there is no
separate build, image, or service to stand up. Deploy = merge to `dev`/
`main`, let `_deploy.yml` build and roll the toolkit stack, then do the
one-time, human steps below (secrets, DNS, Webflow). Re-deploys after that
are just merges; nothing below repeats except the "when it changes" items.

## 1. What ships automatically

`_deploy.yml` (`.github/workflows/_deploy.yml`) triggers on a merge and,
because this module lives under `server/`, always redeploys the `toolkit`
stack:

1. Build the bot's container image (this module's router, static pages and
   `embed.js` are included — `pyproject.toml`'s hatchling `packages =
   ["app"]` ships every non-Python file under `app/`, so no Dockerfile
   change was needed).
2. `tofu apply` the `toolkit` stack (dependency order: base → n8n → toolkit
   → postgres).
3. Run any pending Alembic migration — none is expected for this module,
   `tool_runs` and the `seller_roles` columns already exist.
4. Roll the container and poll `/health` until it passes.

No manual approval gate. Nothing below is part of this automatic path —
it's the one-time setup a human does before/around the first real deploy.

## 2. One-time: secrets

Runtime secrets live only in AWS Secrets Manager, at
`/wusool/<env>/toolkit` (`env` key inside the JSON blob). Add, don't
replace:

```bash
aws secretsmanager get-secret-value --secret-id /wusool/prod/toolkit \
  --query SecretString --output text | jq '.env | keys'
```

Confirm/add these keys under `env`:

| Key | Required? | Notes |
|---|---|---|
| `FIRECRAWL_API_KEY` | Yes, for `/compare` | Without it, `/compare` still serves — comparables just come back empty (the search step is skipped, not the endpoint). |
| `LEAD_MAGNET_FRAME_ANCESTORS` | No (has a default) | Defaults to `https://wusoolcapital.com https://www.wusoolcapital.com` in `config.py` — only set this if the embedding site's origin differs from that default. |

No `CLAUDE_KEY` and no Bedrock access keys — Bedrock is reached through the
EC2 instance's own IAM role (`modules/bedrock-access`), which is already
granted in both `envs/dev.tfvars` and `envs/prod.tfvars`. Adding a key
setting here would recreate the exact problem this migration removes.

A secret edit only takes effect after the bootstrap SSM document re-runs
(`.env.production` is generated at bootstrap, not read live) — see §5.

## 3. One-time: non-secret config (`envs/*.tfvars` + container env)

`server/.env.example` lists every setting `test_env_example.py` enforces.
The ones that matter for a real deploy, beyond the Bedrock model IDs (which
already default correctly):

- **`LEAD_MAGNET_ALLOWED_ORIGINS`** — empty by default, which **disables**
  the same-origin check on `/enrich`, `/analyze`, `/compare`,
  `/readiness/score` and `/buyer/apply` entirely (`api/dependencies.py`).
  Set it to the tools host itself before going live — e.g.
  `https://tools.wusoolcapital.com` in prod — since the tool pages are
  served from that host and their own `fetch()` calls carry it as
  `Origin`, not the Webflow site's origin. This is not a hard security
  boundary (`Origin` is forgeable), just what stops another site spending
  the Bedrock/Firecrawl budget through its own visitors.
- **`LEAD_MAGNET_RATE_PER_HOUR`** (default `20`) — per-IP cap on the
  spend-money endpoints. Raise if a legitimate burst (a marketing push)
  would exceed it.

These aren't Terraform variables — they're container env vars sourced from
the secret's `env` map (see §2) or the compose file's defaults. If you need
a non-default value, add it to the secret's `env` JSON, not a `.tfvars`
file.

## 4. One-time: Terraform — second hostname

The `toolkit` stack already serves this module on a second Caddy hostname
on the same instance (`toolkit_extra_hostnames`,
`infrastructure/terraform/stacks/toolkit/variables.tf`) — no new instance,
no new ECR repo, no new secret:

- **prod**: `envs/prod.tfvars` sets `toolkit_extra_hostnames =
  ["tools.wusoolcapital.com"]` and `toolkit_instance_type = "t3.small"`
  already. Nothing to change here for a normal deploy.
- **dev**: unset — dev serves the tools on its existing bare-IP
  `sslip.io` hostname, no DNS or cert needed.

**Before the prod `tofu apply` that introduces (or changes)
`toolkit_extra_hostnames` runs**, point DNS at the toolkit Elastic IP
first:

```
Cloudflare: A  tools.wusoolcapital.com  -> <prod toolkit EIP>
            Proxy status: DNS only (grey cloud), TTL 60
```

Grey-cloud, not orange-cloud: Caddy requests a Let's Encrypt cert per site
address at config load (HTTP-01). If the DNS record doesn't resolve yet, or
Cloudflare's proxy is in front of it, the cert request fails and Let's
Encrypt's five-failures-per-hostname-per-hour limit kicks in — the fix is
then "wait an hour," not "fix DNS." Grey cloud also means `embed.js`'s 60s
cache-control isn't compounded by Cloudflare's own edge cache, so a
rollback (see §6) doesn't need a manual purge.

If this is already applied (check `terraform state show` for
`module.toolkit["prod"]...extra_hostnames` or just curl the hostname), skip
this step — it's one-time per hostname, not per deploy.

## 5. One-time: re-run the bootstrap document

A Secrets Manager edit or a new `toolkit_extra_hostnames` value only takes
effect once the instance's SSM bootstrap document re-runs (it writes
`.env.production` and the Caddy site config from current secret/tfvars
state, once, at bootstrap — neither is read live). After §2–4:

```bash
aws ssm send-command --document-name wusool-toolkit-bootstrap \
  --instance-ids <toolkit-instance-id> --region eu-central-1
```

(Exact document name/instance id: `terraform output` in `stacks/toolkit`,
or check `modules/toolkit-ec2` for the SSM document resource name if it's
been renamed since this was written.)

## 6. Verify before touching Webflow

```bash
curl -s https://tools.wusoolcapital.com/health
curl -sI https://tools.wusoolcapital.com/embed.js   # cache-control: max-age=60, no X-Frame-Options
curl -sI https://tools.wusoolcapital.com/benchmark/ # 200, Content-Security-Policy: frame-ancestors ...
```

Submit each tool once against prod and confirm one `tool_runs` row and one
Attio record land — `is_test` should be `false` in prod (`ATTIO_IS_TEST`
env var), so don't do this against dev's own data expecting it to mirror.

## 7. Go live in Webflow

Each tool page is already final — `embed.js`'s `TOOLS` map points straight
at `/benchmark/`, `/readiness/`, `/valuation/`, `/buyers/` and
`/get-started/` on this host; there's no separate "old service" fallback
left to switch away from. Going live is pasting the snippet into Webflow,
once per tool, **replacing** (not adding to) whatever Render/Vercel/Tally
embed is there today:

```html
<script src="https://tools.wusoolcapital.com/embed.js" data-tool="benchmark"></script>
```

Do this one tool at a time, benchmark first (it already creates a full
Attio record and exercises the widest field set). **Buyer Network and Get
Started last**, and only after confirming one real submission lands
correctly — both replace a Tally form, so rollback means re-enabling Tally.
Treat them as the point of no return and do them in a low-traffic window.

Get Started is the one tool embedded as a modal rather than inline, because
it replaces a popup rather than a page section. Its snippet carries two
extra attributes, and `data-trigger` must select the button already on the
page:

```html
<script src="https://tools.wusoolcapital.com/embed.js"
        data-tool="get-started" data-modal data-trigger="#get-started-btn"></script>
```

Check the selector against the live markup before pasting: with no matching
element the script does nothing at all, which looks exactly like a button
that was never wired up.

Rollback for any tool: revert that one `<script>` tag in Webflow back to
the old embed. Nothing server-side needs to change.

### Gated reports

Reports live in their own Webflow **Reports** collection
(`6ac64c92647fc1acb46497de`, created 2026-10-07), at `/reports` and
`/reports/<slug>`. Its fields mirror Insights minus `content-type`, `gated`,
`author` and `body-content`. These are one-time Designer changes; nothing is
needed per report:

1. Duplicate the **Insights** page as **Reports** (slug `reports`) and rebind
   both collection lists (featured block and grid) to Reports. The duplicate
   still carries Insights-only bindings; delete or rebind each one:
   - the author name and photo on the cards and the featured block;
   - the content-type badge (`.badge-insights`): delete it, or make it
     static text "Report";
   - any **Hide from listings** filter on the lists, which Reports doesn't have.

   Keep the silo badge (`.badge-silo`), bound to Reports' **Primary Silo**.
   The featured block has no filter; it sorts **Featured** (on first), then
   **Published Date** (newest), with a limit of 1. That way the newest report
   fills the slot when nothing is pinned (2026-10-07).
2. On the **Reports Template** page, remove the article header and author.
   Since 2026-10-08 the navbar and footer sit in a hidden wrapper ("Hidden:
   navbar + footer"), along with the 64px navbar spacer, so a report page
   shows only the report. Show the wrapper again to restore them. In its page settings, bind the SEO
   title, meta description, OG title and OG image to **SEO Title**, **SEO
   Description**, **OG Title** and **OG Image**, as on the Insights Template. Add an Embed set to 100% width.
   It needs no CMS binding: without `data-report`, `embed.js` reads the slug
   from the page URL (`/reports/<slug>`).

   ```html
   <script src="https://tools.wusoolcapital.com/embed.js" data-tool="report"></script>
   ```

   Below it, add the end-of-page button bound to **CTA Text** and **CTA
   URL**, with the visibility condition **CTA URL is set**. The embed already
   carries the gate and the **Download PDF** button.
3. Set `LEAD_MAGNET_SANITY_PROJECT_ID`, `LEAD_MAGNET_SANITY_WEBHOOK_SECRET`,
   `LEAD_MAGNET_SANITY_WRITE_TOKEN` (a Sanity Editor token) and
   `LEAD_MAGNET_WEBFLOW_API_TOKEN` (`CMS:read` + `CMS:write`) in the
   Secrets Manager `env` map. Then add the Sanity webhook described in
   `sanity/README.md`, using its filter and projection exactly.
4. **Home page banner.** The Reports collection (and `Reports (test)`) has a
   **Pin to banner** switch (`pin-to-banner`, added 2026-10-07), set only by
   the sync. On the home page, `div.latest-read` is fixed 68px from the top,
   under the fixed navbar. It has no height or background, so it collapses
   when empty. It holds a Collection List bound to Reports, filtered to
   **Pin to banner** on and sorted by **Published Date** (newest), with a
   limit of 1 and the empty state hidden. The sort means a pin briefly held
   twice still shows the newer report.

   The Collection Item is the visible bar, reading "Just released: {Name}.
   Get the playbook →", and it carries `data-slug` bound to **Slug**. Its
   Embed draws the blue flow and the close button, and remembers the
   dismissed slug in `localStorage`. The Embed script also does two jobs:
   - It points the link at `/reports/<slug>`. The Designer API can't set a
     "current item" link, so the static link stays `/reports`.
   - It adds `has-latest-read` to `<html>`, which pushes the hero down 48px
     on mobile so the bar never covers it.
5. Add the **Insights & Reports** option to `lead_source_detail` in Attio.
   Without it, the org write for every unlock that names an organisation
   fails. A blank organisation writes the person only.
5. Unlock codes go out through SES from `LEAD_MAGNET_EMAIL_FROM`. The
   `wusoolcapital.com` domain is verified in eu-central-1, and the account
   has production access, so codes reach any inbox. The toolkit role's
   existing `ses:SendEmail` grant covers it, and no new secret is needed.

The image now carries headless Chromium (see `server/Dockerfile`), about
590 MB. It runs during a Sanity publish (about 2.4 s for the first playbook)
and for each PDF download (about 0.8 s). Each run uses about 300 MB RAM, one
at a time on the `t3.small`; a download still queued after 30 s fails. The
HTTP container is the same image, so downloads need nothing extra.

#### Moving a report from Insights to Reports

Follow this order. Republishing before the new code is live syncs the report
back into Insights.

1. Build the Reports page and template (steps 1–2 above), then publish the
   site so the Reports collection exists on the live site.
2. Deploy the code that points the sync at Reports to **prod**; a `dev`
   deploy alone isn't enough, since prod would still sync reports into
   Insights. Only then, on both Sanity webhooks (dev and prod), replace the
   filter and projection with the ones in `sanity/README.md`, so they also
   carry Insights articles. Redeploy the
   Studio (`npx sanity deploy -y`) so editors see the Insights type.
3. If the Insights featured block pins the report's old card, pin a
   hand-written article there first, or remove the featured list.
4. Republish the report in Sanity. An unchanged document can't be
   republished, so make a trivial edit (for example, to the excerpt) first.
   The sync creates its card in Reports.
5. Unpublish the old card in the Insights collection.
6. In Webflow **Site settings → Publishing → 301 redirects**, add the exact
   path `/insights/how-to-fund-a-buyout-in-the-uae-and-gcc-2026-playbook` →
   `/reports/how-to-fund-a-buyout-in-the-uae-and-gcc-2026-playbook`, then
   publish the site. Never a wildcard such as `/insights/(.*)`: Insights
   articles still live under `/insights`.

#### Insights articles from Sanity

The Insights collection has a hidden **Sanity managed** switch (added
2026-10-07, off on every existing article). The sync sets it on items it
creates and updates or unpublishes only those, so hand-written articles are
never overwritten. Don't toggle it by hand. The sync never writes
**Featured** or **Hide from listings**; pins stay manual.

Dev writes to test collections only, set in the `/wusool/dev/toolkit`
secret (2026-10-07): `LEAD_MAGNET_WEBFLOW_REPORTS_COLLECTION_ID` is
`Reports (test)` (`6ac65e8154b939a67fa81fbe`) and
`LEAD_MAGNET_WEBFLOW_INSIGHTS_COLLECTION_ID` is `Insights (test)s`
(`6ac4d9fd87ac542edd2f4477`, which has the same switch). Without both
overrides, enabling the dev webhook would write to the live site. Both
environments read the same Sanity dataset, so keep the dev webhook disabled
except while testing.

## 8. The sweeper

`bootstrap.run_sweeper_forever()` is started as a background task in
`server/main.py`'s `_lifespan` and cancelled cleanly on shutdown. It runs
one `sweep_once()` pass immediately at boot (so a restart doesn't wait out
a full interval before draining a backlog), then again every
`LEAD_MAGNET_SWEEPER_INTERVAL_S` (default 300s). Each pass opens and
commits its own session, resumes any run stuck past
`LEAD_MAGNET_SWEEPER_STALE_AFTER_S` from whichever stage it failed at
(never re-spending on Bedrock — see the module README), and abandons
(alerts, stops retrying) anything past its retry ceiling. A pass that
raises is logged and does not stop the loop. Covered by
`tests/unit/test_bootstrap.py` (survives a failed pass, stops cleanly on
cancellation) and `tests/unit/test_sweeper.py` (one pass's behaviour).

Nothing to configure for this beyond the two interval settings already in
`.env.example` — no separate cron, Lambda, or endpoint needed.

## Summary — first deploy vs. every deploy after

**First deploy only:** §2 (secrets), §3 (allowed-origins/rate config), §4
(DNS + `toolkit_extra_hostnames`), §5 (bootstrap re-run), §7 (Webflow
paste).

**Every deploy after that:** merge to `dev`/`main` → `_deploy.yml` does the
rest automatically. Only repeat §5 if a future change edits the secret or
`toolkit_extra_hostnames` again.
