# Publish reports and articles in Sanity

Gated reports and Insights articles are written in the Wusool Reports & Insights Studio
(Sanity), not in Webflow. Publishing in the Studio creates or updates the
page on wusoolcapital.com within a few moments.

## Publish a gated report

1. Create a **Report**, fill in the title, then click **Generate** for the
   slug or type your own.
2. Pick **Write with**: paste the exported report HTML, or write it in the
   rich text editor.
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

Claude Code can publish a report or an article for you, without opening
the Studio. It checks the content against what the site can show, saves a
draft, and publishes only when you say so.

1. Install Node.js LTS from nodejs.org.
2. Copy `.claude/skills/wusool-content/` from the `wusool-infra` repository
   into `~/.claude/skills/` on your computer.
3. Connect the Sanity MCP once:
   `claude mcp add Sanity -t http https://mcp.sanity.io --scope user`.
   Then restart Claude Code, run `/mcp`, and sign in to Sanity.
4. Ask Claude, for example: "Publish an insight in Sanity from
   `article.md`". The first time, Claude checks your setup. It may ask you
   to sign in to the Sanity CLI. It may also ask to add three permission
   rules, so it can save drafts, upload images and publish.
5. Answer Claude's questions and review the checks it shows. For an
   insight, Claude first scores whether it's worth publishing as a blog
   article and suggests fixes. You can go ahead anyway.
6. Give Claude a cover image file, then confirm the draft.
7. Reply "publish" when Claude shows the summary.

**Expected result:** the page is live at `wusoolcapital.com/reports/<slug>`
or `wusoolcapital.com/insights/<slug>`, and Claude confirms it reached
Webflow. A folder named `wusool-content/<date>-<slug>/` keeps the checks
and fields Claude used.
