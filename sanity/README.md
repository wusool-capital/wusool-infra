# Wusool Reports Studio

The dashboard where the business publishes gated insights reports (PRD 3).
One document type, `report`. Publishing one makes it live on
`wusoolcapital.com/insights/<slug>`: the first 25% is open, and the rest
unlocks after a name, email and organisation form.

## How it fits together

1. An editor publishes a report here.
2. Sanity's webhook calls `POST https://tools.wusoolcapital.com/reports/webhooks/sanity`.
3. The toolkit server creates or updates the matching card in the Webflow
   Insights collection with **Gated** on, through the live API. This is
   meant to need no Publish in Webflow, which is not yet verified against
   the live site.
4. The Insights template's embed loads `/report/?slug=<slug>` from the
   toolkit server, which reads the HTML from Sanity and gates it.

Server code: `server/app/modules/lead_magnets/` (`api/insights_report/`,
`providers/sanity/`, `providers/webflow/`).

## One-time setup

1. Create a project at <https://www.sanity.io/manage> (Free plan) with a
   `production` dataset. Free datasets are public. The toolkit server reads
   them without a token.
2. Run the Studio locally, then deploy it:

   ```bash
   npm install
   SANITY_STUDIO_PROJECT_ID=<project id> npm run dev      # http://localhost:3333
   SANITY_STUDIO_PROJECT_ID=<project id> npm run deploy   # <name>.sanity.studio
   ```

3. Invite the editors under **Members** in the Sanity project.
4. Add a webhook under **API → Webhooks**. The free plan allows 2:

   | Setting | Value |
   |---|---|
   | URL | `https://tools.wusoolcapital.com/reports/webhooks/sanity` |
   | Dataset | `production` |
   | Trigger on | Create, Update, Delete |
   | Filter | `_type == "report"` |
   | Projection | `{"slug": after().slug.current, "previousSlug": before().slug.current, "featuredChanged": coalesce(before().featured, false) != coalesce(after().featured, false)}` |
   | HTTP method | `POST` |
   | Secret | a random string, also stored as `LEAD_MAGNET_SANITY_WEBHOOK_SECRET` |
   | Drafts | off |

5. Set the server env in the Toolkit Secrets Manager `env` map:
   - `LEAD_MAGNET_SANITY_PROJECT_ID`
   - `LEAD_MAGNET_SANITY_WEBHOOK_SECRET`
   - `LEAD_MAGNET_WEBFLOW_API_TOKEN`, a Webflow site token with `CMS:read` and `CMS:write`

## Publishing a report

Fill in the title, slug, excerpt and the pasted HTML. Cover image, author,
primary silo and date are optional. Tick **Pin to top of /insights** to make
it the featured card; that unpins the current one. Then publish.

The pin only moves when you tick or untick it. When a newer report takes the
pin, the older report still shows the box ticked here; editing it later
won't take the pin back. To pin it again, untick, publish, then tick and
publish.

- **Renaming a slug** unpublishes the old card and creates a new one, so
  the old URL stops working.
- **Unpublishing or deleting** a report unpublishes its card.

## Accepted risk

On the Free plan the dataset is public. The project ID ships in this
Studio's public bundle, so a technical person could read full reports
without the form. A private dataset (Growth plan) plus a read token in
`providers/sanity/report_source.py` closes this. Nothing else changes.
