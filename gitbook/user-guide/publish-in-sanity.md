# Publish reports and articles in Sanity

Gated reports and Insights articles are written in the Wusool Reports Studio
(Sanity), not in Webflow. Publishing in the Studio creates or updates the
page on wusoolcapital.com within a few moments.

## Publish a gated report

1. Create a **Report**, fill in the title, then click **Generate** for the
   slug or type your own.
2. Pick **Write with**: paste the exported report HTML, or write it in the
   rich text editor. Either way, new readers see the first page before the
   form.
3. Optionally fill in the excerpt, cover image, primary silo, date, and the
   end-of-page button (text and link).
4. Optionally tick:
   - **Pin to top of /reports** to make it the featured card on the reports
     page.
   - **Pin to home page banner** to show "Just released: {title}. Get the
     playbook →" across the top of the home page. Visitors can close the
     bar; it returns when a different report is pinned.

   Each pin moves from whichever report held it before.
5. Publish.

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
- **Unpublishing** removes its card from `/reports`. If it was pinned, the
  newest live report takes the pin.

## Publish an Insights article

1. Create an **Insights article** and fill in the title, slug, content type
   and excerpt.
2. Pick **Write with**: the rich text editor, or pasted HTML. Then write the
   body, and optionally the key takeaways and FAQ.
3. Optionally fill in the cover image, author, silo, SEO fields and the
   end-of-page button. Blank SEO fields use the title and excerpt.
4. Publish.

**Expected result:** the article appears on `wusoolcapital.com/insights`.
Articles are not gated. To pin an article, use Webflow. An existing
hand-written Webflow article with the same slug is never overwritten.
