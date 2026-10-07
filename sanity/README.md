# Wusool Reports Studio

The dashboard where the business publishes gated insights reports (PRD 3).
One document type, `report`. Publishing one makes it live on
`wusoolcapital.com/reports/<slug>`: the first page is open, and the rest
and the PDF download unlock after a name and email form (organisation is
optional).

## How it fits together

1. An editor publishes a report here.
2. Sanity's webhook calls `POST https://tools.wusoolcapital.com/reports/webhooks/sanity`.
3. The toolkit server opens the pasted HTML once in headless Chromium and
   saves what it draws back to the report as static HTML, in the hidden
   `renderedHtml` field (with `renderedPreviewEnd`, where the free part ends). This is how exports that build their pages with
   JavaScript, like "Buyouts in the GCC", become splittable. It then creates
   or updates the matching card in the Webflow Reports collection, through
   the live API. This is
   meant to need no Publish in Webflow, which is not yet verified against
   the live site.
4. The Reports template's embed loads `/report/?slug=<slug>` from the
   toolkit server, which reads the HTML from Sanity and gates it.

Server code: `server/app/modules/lead_magnets/` (`api/insights_report/`,
`providers/sanity/`, `providers/webflow/`).

## One-time setup

1. The project is **Insights and Reports** (`itidwo8t`) on the Free plan, with
   a public `production` dataset. The toolkit server reads it without a token.
2. Run the Studio locally, then deploy it:

   ```bash
   npm install
   npx sanity login                          # once per machine
   npm run dev                               # http://localhost:3333
   npx sanity deploy -y                      # https://wusool-reports.sanity.studio (live)
   ```

3. Invite the editors under **Members** in the Sanity project.
4. Two webhooks already exist, **disabled and without a secret**: "Report sync
   (dev)" → `https://63-184-6-136.sslip.io/...` and "Report sync (prod)" →
   `https://tools.wusoolcapital.com/...`. For each environment, once its
   server is deployed: edit the webhook, set a secret (same value as that
   environment's `LEAD_MAGNET_SANITY_WEBHOOK_SECRET`), and enable it. For
   reference, their settings are (the free plan allows 2):

   | Setting | Value |
   |---|---|
   | URL | `https://tools.wusoolcapital.com/reports/webhooks/sanity` (dev: `https://63-184-6-136.sslip.io/reports/webhooks/sanity`) |
   | Dataset | `production` |
   | Trigger on | Create, Update, Delete |
   | Filter | `_type == "report" && (delta::operation() != "update" \|\| delta::changedAny((title, slug, html, excerpt, cover, author, silo, publishedAt, featured, cta)) \|\| !defined(renderedHtml))` |
   | Projection | `{"slug": after().slug.current, "previousSlug": before().slug.current, "featuredChanged": coalesce(before().featured, false) != coalesce(after().featured, false)}` |
   | HTTP method | `POST` |
   | Secret | a random string, also stored as `LEAD_MAGNET_SANITY_WEBHOOK_SECRET` |
   | Drafts | off |
   | API version | `v2025-02-19` |

   The filter skips updates that touch only `renderedHtml`, so the server's
   own save never starts a second sync. Creates and deletes always pass,
   since `delta::changedAny` doesn't match them reliably; an unpublish fires
   as a delete. `!defined(renderedHtml)` catches a report whose rendered copy
   was dropped, for example when an older draft is published over it.

5. Set the server env in the Toolkit Secrets Manager `env` map:
   - `LEAD_MAGNET_SANITY_PROJECT_ID`
   - `LEAD_MAGNET_SANITY_WEBHOOK_SECRET`
   - `LEAD_MAGNET_SANITY_WRITE_TOKEN`, an **Editor** API token (API → Tokens).
     It is used only to save the flattened report back.
   - `LEAD_MAGNET_WEBFLOW_API_TOKEN`, a Webflow site token with `CMS:read` and `CMS:write`

## Publishing a report

Fill in the title, slug, excerpt and the pasted HTML. Cover image,
primary silo, date and the end-of-page button are optional. The button
needs both its text and its link, and shows below the report. Removing it
here doesn't remove it from the live page; clear it in Webflow as well. Tick **Pin to top of /reports** to make
it the featured card; that unpins the current one. Then publish.

The pin only moves when you tick or untick it. When a newer report takes the
pin, the older report still shows the box ticked here; editing it later
won't take the pin back. To pin it again, untick, publish, then tick and
publish.

The featured slot is never left empty. When you untick, unpublish or delete
the pinned report, the newest live card on `/reports` takes the pin.

- **Renaming a slug** unpublishes the old card and creates a new one, so
  the old URL stops working.
- **Unpublishing or deleting** a report unpublishes its card.

## Accepted risk

On the Free plan the dataset is public. The project ID ships in this
Studio's public bundle, so a technical person could read full reports
without the form. A private dataset (Growth plan) plus a read token in
`providers/sanity/report_source.py` closes this. Nothing else changes.
