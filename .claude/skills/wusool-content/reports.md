# Reports flow

Use `reference.md` for every field rule and for how to create, upload and publish.
`<dir>` is the working folder from `SKILL.md`.

## 1. Pick the format

- An exported HTML file (`.html`) → `bodyFormat: "html"`.
- Pasted text, Markdown or a document → `bodyFormat: "rich"`.

Copy an HTML input to `<dir>/report.html` and work only on that copy.

## 2. Check HTML (`bodyFormat: "html"`)

Exported reports are often around 1 MB. **Never read the whole file**: use `wc -c` and
short `grep -o` / `grep -c` patterns, and never print matching lines in full (a single
line can be the whole bundle). Run from `<dir>`:

```bash
wc -c report.html
# Meta refresh: stripped on render; the page must not depend on it
grep -ciE 'http-equiv=["'\'']?refresh' report.html
# External hosts
grep -oiE '(src|href)=["'\'']?https?://[^/"'\'' >]+' report.html | sort | uniq -c
# Page viewer (shadow DOM)
grep -c 'attachShadow' report.html
# Title and headings
grep -oiE '<title>[^<]{0,200}</title>' report.html
grep -oiE '<h[1-3][^>]{0,80}>[^<]{1,120}' report.html | head -20
# Fonts and brand colours (advisory)
grep -oiE 'font-family:[^;"]{1,80}' report.html | sort | uniq -c | head
grep -oiE '#(000523|c6e1ee|f7f5f0)' report.html | sort | uniq -c
```

What each result means:

- **External hosts:** any host other than `fonts.googleapis.com`, `fonts.gstatic.com` or
  `cdn.sanity.io` is blocked while rendering, so a script or image from it won't appear.
  Stylesheets from it load for readers but are missing in the PDF.
- **Page viewer:** `0` means no page viewer, so `freePages` is ignored and the form falls
  at the first block. Tell the person.
- **Title:** use it to suggest `title`; warn if missing.
- **Fonts and colours:** warn only if it's not DM Sans or Inter, or uses none of the brand
  colours.

Ask the person for `freePages` (default 1). With a page viewer, it must leave at least
the last page locked.

## 3. Check rich text (`bodyFormat: "rich"`)

- Convert the content to Portable Text as `reference.md` describes: allowed styles,
  lists, marks and links only, every item with a `_key`.
- Turn `h1` into the `title` (or `h2` if a title already exists). Turn tables into
  lists. Ask for each image file and upload it.
- Ask for `lockedPercent` (10–90, default 75).

## 4. Fields and slug

Propose `title`, `slug`, `excerpt`, `seoTitle` (≤ 60), `seoDescription` (≤ 155), `silo`,
and an optional `cta`. Ask for a cover image file, and whether to pin the home banner
(default no).

Check the slug is free:

```groq
count(*[_type == "report" && slug.current == $slug])
```

It must be `0` (the count covers drafts too). If it's taken, propose another.

Write to `<dir>`:

- `fields.json`: the full document, with `_id` and `_type`, minus `html`.
- `checks.md`: each check above and its result.

Show the person `checks.md` and the fields, and wait for an OK before writing.

## 5. Write the draft

Upload the cover (and any rich-text images), then create the draft as `reference.md`
describes. For HTML, merge `html` from `report.html`. Always include `bodyFormat`,
`publishedAt` and `bannerPinned`.

For HTML, confirm it arrived intact:

```groq
*[_id == $draftId]{"len": length(html)}
```

against `node -p 'require("fs").readFileSync("<dir>/report.html", "utf8").length'`. They
should match; emoji can cause a small difference. If they differ by more than that,
rebuild `doc.json` and rerun with `--replace`.

## 6. Publish (with approval)

Follow **Publish** in `reference.md`. Then confirm the render, using the published id
(no `drafts.`):

```groq
*[_id == $id][0]{renderedFrom, renderedPreviewEnd, "renderedLen": length(renderedHtml)}
```

The server renders after each publish, which can take a minute or two. Don't sleep in
the foreground: re-run the query from a background or Monitor wait if your tools have
one, or tell the person it's rendering and re-check when they reply. Wait until
`renderedFrom` is set (on a republish, until it changes). Then:

- `renderedPreviewEnd` is where the free preview ends in `renderedHtml`. A very small
  share of `renderedLen` means the gate fell at the first block: tell the person.
- Check Webflow: the Reports collection's **list collection items** action filtered by
  `slug` should return the item. If the Webflow MCP isn't connected, say this check
  didn't run.

Give the person the live URL: `https://www.wusoolcapital.com/reports/<slug>`.
