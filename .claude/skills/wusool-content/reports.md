# Reports flow

Use `reference.md` for every field rule and for how to upload, create and publish.

## 1. Pick the format

- An exported HTML file, attached → `bodyFormat: "html"`. It goes up as `htmlFile`.
- Pasted text, Markdown or a document → `bodyFormat: "rich"`.

## 2. Check HTML (`bodyFormat: "html"`)

Exported reports are often around 1 MB. **Never read the whole file into the
conversation**: run these in the code tool on the attached file, and never print
matching lines in full (a single line can be the whole bundle).

```bash
F=report.html   # the attached file's path in the code tool
wc -c "$F"
# Meta refresh: stripped on render; the page must not depend on it
grep -ciE 'http-equiv=["'\'']?refresh' "$F"
# External hosts
grep -oiE '(src|href)=["'\'']?https?://[^/"'\'' >]+' "$F" | sort | uniq -c
# Page viewer (shadow DOM)
grep -c 'attachShadow' "$F"
# Title and headings
grep -oiE '<title>[^<]{0,200}</title>' "$F"
grep -oiE '<h[1-3][^>]{0,80}>[^<]{1,120}' "$F" | head -20
# Fonts and brand colours (advisory)
grep -oiE 'font-family:[^;"]{1,80}' "$F" | sort | uniq -c | head
grep -oiE '#(000523|c6e1ee|f7f5f0)' "$F" | sort | uniq -c
```

Record every result in `checks.md`. Tell the person only the problems, in plain words
(such as "the charts load from another site and won't show"), and say "Everything else
checks out." in one line.

What each result means:

- **Size:** over 20 MB is refused by the server.
- **External hosts:** any host other than `fonts.googleapis.com`, `fonts.gstatic.com` or
  `cdn.sanity.io` is blocked while rendering, so a script or image from it won't appear.
  Stylesheets from it load for readers but are missing in the PDF.
- **Page viewer:** `0` means no page viewer, so `freePages` is ignored and the form falls
  at the first block. Tell the person the sign-up form will appear right after the
  opening section.
- **Title:** use it to suggest `title`; warn if missing.
- **Fonts and colours:** warn only if it's not DM Sans or Inter, or uses none of the brand
  colours.

`freePages` is a staff field (default 1). With a page viewer, it must leave at least the
last page locked.

## 3. Check rich text (`bodyFormat: "rich"`)

- Convert the content to Portable Text as `reference.md` describes: allowed styles,
  lists, marks and links only, every item with a `_key`.
- Turn `h1` into the `title` (or `h2` if a title already exists). Turn tables into
  lists. Ask the person to attach each image.
- `lockedPercent` is a staff field (10–90, default 75).

## 4. Fields and slug

Ask for the reports **staff fields** in `reference.md`, as that section describes.
Limits: `seoTitle` ≤ 60, `seoDescription` ≤ 155.

Check the slug is free:

```groq
count(*[_type == "report" && slug.current == $slug])
```

It must be `0` (the count covers drafts too). If it's taken, propose another web
address in one line.

One message, before writing: any check that failed (passed ones in one line), the
staff-field table, and "Still blank: … Leave these blank?". Wait for an OK.

## 5. Write the draft

1. Upload the cover (if given), any rich-text images and, for HTML, the report file as `file`.
2. Create the draft with every field, including `bodyFormat`, `publishedAt`,
   `bannerPinned` and, for HTML, `htmlFile`. Never set `html`.
3. For HTML, confirm the upload is the whole file:

   ```groq
   *[_id == $draftId][0]{"size": htmlFile.asset->size}
   ```

   It must equal the `wc -c` size. If not, upload again and patch `htmlFile`.

## 6. Publish (with approval)

Follow **Publish** in `reference.md`. Then confirm the render, using the published id
(no `drafts.`):

```groq
*[_id == $id][0]{renderedFrom, renderedPreviewEnd, "renderedLen": length(renderedHtml)}
```

The server renders after each publish, which can take a minute or two. Wait about 20
seconds between checks (the code tool can `sleep`), for up to about 3 minutes, until
`renderedFrom` is set (on a republish, until it changes). Then:

- `renderedPreviewEnd` is where the free preview ends in `renderedHtml`. A very small
  share of `renderedLen` means the gate fell at the first block: tell the person the
  sign-up form appears almost at the top.
- If it never renders, tell the person the report isn't showing on the site yet and
  that publishing again retries it. Put the likely cause in `checks.md`: the server may
  not be deployed with `htmlFile` support yet, or the sync failed.
- Check Webflow: the Reports collection's **list collection items** action filtered by
  `slug` should return the item. Without the Webflow connector, say this check didn't run.

Give the person the live URL: `https://www.wusoolcapital.com/reports/<slug>`.
