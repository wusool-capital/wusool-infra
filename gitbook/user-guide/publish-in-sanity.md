# Publish reports and articles in Sanity

Gated reports and Insights articles are written in the Wusool Reports & Insights Studio
(Sanity), not in Webflow. Publishing in the Studio creates or updates the
page on wusoolcapital.com within a few moments.

## Publish a gated report

1. Create a **Report**, fill in the title, then click **Generate** for the
   slug or type your own.
2. Pick **Write with**: the exported report HTML, or the rich text editor.
   Paste the HTML, or upload it as a file in **Report HTML file**.
3. Choose how much is free. For pasted HTML, **Free pages** is how many
   pages readers see before the form (1 if blank; the last page always
   stays locked). For rich text, **Locked share (%)** is how much sits behind
   the form, by text length (75 if blank).
4. Optionally fill in the excerpt, cover image, primary silo, date, and the
   end-of-page button (text and link). The **SEO** tab sets the search and
   share titles; blank ones use the title and excerpt.
5. Optionally tick **Pin to home page banner** to show "Just released:
   {title}. Get the playbook →" across the top of the home page. It moves
   from whichever report held it before. Visitors can close the bar; it
   returns when a different report is pinned. The top of `/reports` always
   shows the newest report.
6. Publish.

**Expected result:** the report has a card on `wusoolcapital.com/reports`
and its own page at `wusoolcapital.com/reports/<slug>`. See
[Website lead tools](lead-tools.md#read-a-gated-report) for what readers
see.

## Change or remove a report

- **Edit and republish** to update the live page. Layout improvements to
  the report page also reach a published report only once it is
  republished.
- **Changing the slug** moves the report to the new URL, and the old URL
  stops working.
- **Unpublishing** removes its card from `/reports`. If it held the
  banner, the banner is hidden until another report is pinned.

## Publish an Insights article

1. Create an **Insights article** and fill in the title, slug, content type
   and excerpt.
2. Pick **Write with**: the rich text editor, or pasted HTML. Then write the
   body, and optionally the key takeaways and FAQ.
3. Optionally fill in the cover image, author, silo, SEO fields and the
   end-of-page button. Blank SEO fields use the title and excerpt.
4. Optionally tick **Pin to top of /insights** to make it the featured
   article. It replaces whichever article is pinned now, hand-written ones
   included.
5. Publish.

**Expected result:** the article appears on `wusoolcapital.com/insights`.
Articles are not gated. Unticking the pin, or unpublishing the pinned
article, leaves nothing pinned, and the newest article shows at the top
instead. An existing
hand-written Webflow article with the same slug is never overwritten.

## Publish with Claude

Claude can publish a report or an article for you from a normal Claude chat,
without opening the Studio. It checks the content against what the site can
show, saves a draft, and publishes only when you say so.

### One-time setup (Claude org owner)

1. In **Organization settings → Capabilities → Code execution**, turn on
   network egress and add `mcp.sanity.io` under **Additional allowed
   domains**. Claude uploads report files and images there.
2. In the admin settings, add Sanity as a custom connector:
   `https://mcp.sanity.io`. Add the Webflow connector too, so Claude can
   check for duplicate articles.
3. Zip the `.claude/skills/wusool-content/` folder from the `wusool-infra`
   repository and add it as an organization skill. Staff without it can
   upload the same zip under **Customize → Skills**.

### Publish a report or an article

1. Start a new chat and connect your Sanity account when Claude asks.
2. Ask Claude, for example: "Publish this insight" or "Publish this report",
   and attach the file or paste the text.
3. Answer Claude's questions and review the checks it shows. For an
   insight, Claude first scores whether it's worth publishing as a blog
   article and suggests fixes. You can go ahead anyway.
4. Attach a cover image, then confirm the draft.
5. Reply "publish" when Claude shows the summary.

**Expected result:** the page is live at `wusoolcapital.com/reports/<slug>`
or `wusoolcapital.com/insights/<slug>`, and Claude confirms it reached
Webflow. Claude also offers the checks and fields it used as files to
download.
