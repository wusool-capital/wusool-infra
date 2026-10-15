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
- Ask for each image file and where it goes; upload it as `reference.md` describes.

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

Ask for a cover image file. Then write to `<dir>`:

- `fields.json`: the full document, with `_id` and `_type`. For HTML, leave out
  `bodyHtml`; it's merged from `source.html`.
- `checks.md`: each check and its result.

Show the person `checks.md` and the fields, and wait for an OK before writing.

## 7. Write the draft

Upload the cover and any images, then create the draft as `reference.md` describes.
Always include `bodyFormat`, `contentType`, `publishedAt` and `featured`. For HTML, merge
`bodyHtml` from `source.html`.

## 8. Publish (with approval)

Follow **Publish** in `reference.md`. Then confirm it reached Webflow: the Insights
collection's **list collection items** action filtered by `slug` should return the item
within a minute. If it doesn't, the slug may belong to a hand-written article (the sync
skips it silently); tell the person. If the Webflow MCP isn't connected, say this check
didn't run.

Give the person the live URL: `https://www.wusoolcapital.com/insights/<slug>`.
