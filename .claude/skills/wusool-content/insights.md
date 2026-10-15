# Insights flow

Use `reference.md` for every field rule. `<dir>` is the working folder from `SKILL.md`.

## 1. Pick the format

Default to `bodyFormat: "rich"`: convert the input to Portable Text. Use `"html"` only
when the person wants to keep pasted HTML as it is. The choice covers the body, key
takeaways and FAQ together.

Save the input as `<dir>/source.md` (or `source.html`).

Then follow `blog-worthiness.md`. Continue only on a **Publish** verdict, or when the
person chooses to go ahead anyway.

## 2. Check the content

**Rich (`"rich"`):** convert to Portable Text as `reference.md` describes.
- Allowed styles, lists, marks and links only; every item gets a `_key`.
- `h1` becomes the `title` (or `h2`). Tables become lists or short paragraphs.
- List each image the person must add in the Studio, with where it goes.

**HTML (`"html"`):** list every tag or attribute the server will strip (see the allowed
list in `reference.md`) and what the reader loses, such as a table's layout.

**Either:** if the input has a key-takeaways or FAQ section, move it into
`keyTakeaways` / `faq` instead of the body. Both are optional.

## 3. Fields

Propose: `title`, `slug`, `contentType` (default `Article`), `excerpt` (required),
`author`, `silo`, `h1`, `seoTitle` (≤ 60), `seoDescription` (≤ 155), `ogTitle`,
`targetKeyword`. Ask whether to pin it to the top of /insights (default no).
`author` and `silo` take only the listed values; leave them blank rather than guess.

## 4. Slug: unique in Sanity and Webflow

1. Sanity, which also counts drafts:

   ```groq
   count(*[_type == "insights" && slug.current == $slug])
   ```

   Must be `0`.
2. Webflow: with the Webflow MCP's CMS **list collection items** action, filter
   collection `69aaa645fa60624091050e8e` by `slug` equal to the slug. It must return
   no items: a hand-written article with this slug would silently block the sync.
   If the Webflow MCP isn't connected, say so plainly and write "Webflow slug check
   **not run**" in `checks.md`.

If either is taken, propose another slug.

## 5. Insight + report

When the person said yes to "Is this insight + report?":

1. Check the report is **published**, using the `published` perspective:

   ```groq
   *[_type == "report" && slug.current == $reportSlug][0]{_id, title}
   ```

   If it returns nothing, check for a draft (raw perspective). If only a draft exists,
   tell the person to publish the report first; the link would 404 until then. Stop
   until they confirm.
2. Set `cta: {"text": "Download the full report", "url": "/reports/<reportSlug>"}`.
3. Add one inline link to `/reports/<reportSlug>` in the body, where the article first
   mentions the report (rich: a `link` markDef; HTML: an `<a href>`). Show the person
   the sentence.

## 6. Save and confirm

Write to `<dir>`:

- `fields.json`: the full document content you'll send.
- `checks.md`: each check, its result, and what the person must do by hand.

Show the person `checks.md` and the fields, and wait for an OK before writing.

## 7. Write the draft

Create one `insights` document with the Sanity MCP's **create documents** tool:
`projectId: itidwo8t`, `dataset: production`. Always include `bodyFormat`,
`contentType`, `publishedAt` and `featured`.

If the JSON is near 100 KB, create it without `body`, then add the body with
**patch documents**: `setIfMissing: {"body": []}`, then
`insert: {after: "body[-1]", items: [...]}` in batches under 90 KB. If `bodyHtml` alone
is over 90 KB, create without it and ask the person to paste `source.html` into
**Body (HTML)** in the Studio.

## 8. Hand off

Never publish. Give the person:

1. The Studio link (see `reference.md`), with the id minus `drafts.`.
2. What's left: add the cover and any images, review, then **Publish**. Without a cover,
   the Webflow card and share image are blank.
3. A reminder: the page appears at `wusoolcapital.com/insights/<slug>` only after publishing.
