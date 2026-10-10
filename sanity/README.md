# Wusool Reports Studio

The dashboard where the business publishes gated reports (PRD 3) and
Insights articles. Two document types:

- **Report** (`report`). Publishing one makes it live on
  `wusoolcapital.com/reports/<slug>`: the free part is open, and the rest
  and the PDF download unlock after a name and email form (organisation is
  optional).
- **Insights article** (`insights`). Publishing one creates or updates the
  article at `wusoolcapital.com/insights/<slug>`, written with the rich text
  editor or as pasted HTML.

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
   | Filter | `(_type == "report" && (delta::operation() != "update" \|\| delta::changedAny((title, slug, bodyFormat, body, html, excerpt, cover, silo, publishedAt, featured, bannerPinned, cta, seoTitle, seoDescription, ogTitle, freePages, lockedPercent)) \|\| !defined(renderedHtml))) \|\| _type == "insights"` |
   | Projection | `{"type": coalesce(after()._type, before()._type), "slug": after().slug.current, "previousSlug": before().slug.current}` |
   | HTTP method | `POST` |
   | Secret | a random string, also stored as `LEAD_MAGNET_SANITY_WEBHOOK_SECRET` |
   | Drafts | off |
   | API version | `v2025-02-19` |

   One webhook per environment serves both types; the server routes each
   event by `type`, and treats a missing `type` as a report. Articles need no
   update guard: the server writes to them only to move the `/insights` pin,
   and the sync each such write starts is the one that updates Webflow. The filter
   skips report updates that touch only `renderedHtml`, so the server's
   own save never starts a second sync. Creates and deletes always pass,
   since `delta::changedAny` doesn't match them reliably; an unpublish fires
   as a delete. `!defined(renderedHtml)` catches a report whose rendered copy
   was dropped, for example when an older draft is published over it.

5. Set the server env in the Toolkit Secrets Manager `env` map:
   - `LEAD_MAGNET_SANITY_PROJECT_ID`
   - `LEAD_MAGNET_SANITY_WEBHOOK_SECRET`
   - `LEAD_MAGNET_SANITY_WRITE_TOKEN`, an **Editor** API token (API → Tokens).
     It saves the flattened report back and moves the `/insights` pin.
   - `LEAD_MAGNET_WEBFLOW_API_TOKEN`, a Webflow site token with `CMS:read` and `CMS:write`

## Publishing a report

Pick **Write with** first. **Pasted HTML** (the default) keeps an exported
design and its pages: readers see the free pages, then the form. **Rich text
editor** writes the report in the Studio: it gets a clean page with the title
on top, readers see the unlocked part (the first quarter by default), and the
PDF is printed with page margins.

How much is free is set per report:

- **Free pages** (pasted HTML): how many pages readers see before the form.
  Blank means 1. The last page always stays behind the form, so a number
  larger than the report locks only its last page. An export without pages
  opens its first block.
- **Locked share (%)** (rich text): how much of the report sits behind the
  form, from 10 to 90, measured by text length. Blank means 75. The cut
  never falls inside a list.

Changing either one re-renders the report on the next publish.

Only the title and the report (pasted HTML or rich text) are needed. For the slug, click
**Generate** to build it from the title, or type your own (lowercase letters,
numbers and hyphens). Excerpt, cover image, primary silo, date and the end-of-page
button are optional. The **SEO** tab sets the SEO title, SEO description and
share title; left blank, they use the title and excerpt. The button
needs both its text and its link, and shows below the report. Removing it
here doesn't remove it from the live page; clear it in Webflow as well. Then publish.

Two boxes pin a report, one report per pin:

- **Pin to top of /reports** makes it the featured card. With nothing
  pinned, the newest report shows there instead.
- **Pin to home page banner** shows it in the bar at the top of the home
  page ("Just released: …"). With nothing pinned, the bar is hidden.

Publishing a pinned report unticks that box on the report that had the pin,
here as well as on the site, so the boxes always show the truth. One
exception: a draft of that older report edited after your pin keeps its
tick, and publishing that draft takes the pin back.

- **Renaming a slug** unpublishes the old card and creates a new one, so
  the old URL stops working.
- **Unpublishing or deleting** a report unpublishes its card.

## Publishing an Insights article

Fill in the title, slug, content type, excerpt and body. Pick **Write with**
first: the rich text editor, or pasted HTML. The choice applies to the body,
key takeaways and FAQ. Pasted HTML is cleaned on publish: scripts, styles,
tables and anything else Webflow's rich text can't show are removed.

The SEO title, SEO description, share title and H1 default to the title and
excerpt when left blank. Cover image, author, silo, date, target keyword and
the end-of-page button are optional. Then publish.

- The article goes live on `/insights` without a Webflow publish.
- A hand-written Webflow article with the same slug is never overwritten.
  The publish is skipped and logged as `insights_article_sync_skipped_unmanaged`.
- **Renaming a slug** or **unpublishing** works as it does for reports.
- Sanity owns these articles: the next publish overwrites any edit made to
  them in Webflow.
- Clearing an optional field here (key takeaways, FAQ, cover, author, silo,
  SEO fields, button) doesn't clear it on the site. Clear it in Webflow too.
- Key takeaways and FAQ get a "Key Takeaways" / "FAQ" heading, as on
  hand-written articles, unless they already start with a Heading 2.

### Pinning an article

**Pin to top of /insights** (Publishing tab) makes the article the one card
in the featured block. One article holds the pin at a time:

- Publishing a pinned article unpins every other article on the site,
  hand-written ones included, and unticks the box on other Sanity articles.
  As with reports, the later of two pins wins.
- When the pinned article is unticked, unpublished or deleted, and nothing
  else holds the pin, the newest other Sanity article takes it (its box is
  ticked here). With no Sanity article, the newest listed hand-written
  article is pinned in Webflow instead.
- Pinning a hand-written article in Webflow still works. A later Sanity pin
  replaces it, and it doesn't come back on its own.

## Accepted risk

On the Free plan the dataset is public. The project ID ships in this
Studio's public bundle, so a technical person could read full reports
without the form. A private dataset (Growth plan) plus a read token in
`providers/sanity/report_source.py` closes this. Nothing else changes.
