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
at `/benchmark/`, `/readiness/`, `/valuation/`, `/buyers/` on this host;
there's no separate "old service" fallback left to switch away from. Going
live is pasting the snippet into Webflow, once per tool, **replacing** (not
adding to) whatever Render/Vercel/Tally embed is there today:

```html
<script src="https://tools.wusoolcapital.com/embed.js" data-tool="benchmark"></script>
```

Do this one tool at a time, benchmark first (it already creates a full
Attio record and exercises the widest field set). **Buyer Network last**,
and only after confirming one real submission lands correctly — its
rollback also means re-enabling Tally, so treat it as the point of no
return and do it in a low-traffic window.

Rollback for any tool: revert that one `<script>` tag in Webflow back to
the old embed. Nothing server-side needs to change.

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
