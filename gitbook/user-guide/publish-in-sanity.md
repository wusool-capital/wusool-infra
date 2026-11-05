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
4. For an uploaded HTML file, optionally tick **Keep it interactive**.
   After the form, readers get the live report, with its charts and
   clicks. The free preview stays flat, and the PDF is always flat.
5. Optionally fill in the excerpt, cover image, primary silo, date, and the
   end-of-page button (text and link). The **SEO** tab sets the search and
   share titles; blank ones use the title and excerpt.
6. Optionally tick **Pin to home page banner** to show "Just released:
   {title}. Get the report →" across the top of the home page. Change the
   link wording in **Banner button text** (blank means "Get the report"; the
   site adds the arrow). It moves from whichever report held it before. Visitors can close the bar; it
   returns when a different report is pinned. The top of `/reports` always
   shows the newest report.
7. Publish.

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
2. Pick **Write with**: the rich text editor, pasted HTML, or **HTML file
   as the whole page**. Then write the body. Optionally add the key takeaways
   and FAQ. For the whole page, upload the exported file in
   **Charts HTML file** instead. The article page then shows that file as it
   looks in a browser, sidebar and charts included. Its links open in a new
   tab. Tick **Hide header and author details** to show only the site navbar
   above it.
3. Optionally fill in the cover image, author, silo, SEO fields and the
   end-of-page button. Blank SEO fields use the title and excerpt.
4. For an article with live charts, upload the exported file in
   **Charts HTML file**. Then add a **Chart from the HTML file** block in the
   body where each chart goes. Turn **Interactive** off for charts that
   don't react to clicks. Charts show as pictures first and turn live as
   the reader scrolls to them.
5. Optionally tick **Pin to top of /insights** to make it the featured
   article. It replaces whichever article is pinned now, hand-written ones
   included.
6. Publish.

**Expected result:** the article appears on `wusoolcapital.com/insights`.
Articles are not gated. Unticking the pin, or unpublishing the pinned
article, leaves nothing pinned, and the newest article shows at the top
instead. An existing
hand-written Webflow article with the same slug is never overwritten.

## Publish with Claude

Reports and Insights articles, straight from a Claude chat. No Sanity Studio
needed.

### One-time setup (about 5 minutes)

1. Make sure you have a **Sanity account** in the **Insights and Reports**
   project. If you don't, ask the tech team (tech@wusoolcapital.com).
2. In Claude, open **Settings → Connectors (Select Discover)**, connect
   **Sanity** and sign in with that account.
3. Save the **wusool-content.zip** file you were sent. In Claude, open
   **Customize → Skills**, upload the zip as it is (don't unzip it), and turn
   **wusool-content** on.
4. Open **Settings → Capabilities** and turn on **Code execution and file
   creation**.

### Publish a report or an article

1. Start a **new chat**.
2. Attach your file (Word, Markdown or the exported report HTML) or paste the
   text. Then type **"Publish this insight"** or **"Publish this report"**.
3. Answer Claude's questions. For an article, Claude first tells you whether
   it's worth publishing.
4. Fill in the details Claude lists: title, excerpt, SEO title and so on. For
   anything you leave blank, Claude tells you what happens.
5. Check the draft, then reply **"publish"**. **Nothing goes live until you
   do.**

**Expected result:** the page is live at `wusoolcapital.com/reports/<slug>`
or `wusoolcapital.com/insights/<slug>`.

### Good to know

- Claude confirms when the page is live and gives you the link.
- If Claude says an upload was **blocked**, start a new chat. If it happens
  again, tell the tech team.

{% hint style="info" %}
**For the tech team:** uploads need `mcp.sanity.io` under **Organization
settings → Capabilities → Code execution → Additional allowed domains**, with
network egress on.
{% endhint %}
