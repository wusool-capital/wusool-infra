# Reports flow

Use `reference.md` for every field rule. `<dir>` is the working folder from `SKILL.md`.

## 1. Pick the format

- An exported HTML file (`.html`) → `bodyFormat: "html"`.
- Pasted text, Markdown or a document → `bodyFormat: "rich"`.

Copy an HTML input to `<dir>/report.html` and work only on that copy.

## 2. Check HTML (`bodyFormat: "html"`)

Exported reports are often around 1 MB. **Never read the whole file**: use `wc -c`
and `grep -o` / `grep -c` with short patterns, and never print matching lines in full
(a single line can be the whole bundle).

| Check | How | If it fails |
|---|---|---|
| Size | `wc -c report.html` | Over 60 KB → it goes through the Studio paste (step 5) |
| Meta refresh | `grep -ciE 'http-equiv=["'\'']?refresh'` | Warn: it's stripped; the page must not depend on it |
| External hosts | `grep -oiE '(src\|href)=["'\'']?https?://[^/"'\'' >]+' \| sort \| uniq -c` | Any host other than `fonts.googleapis.com`, `fonts.gstatic.com` or `cdn.sanity.io` is blocked: a script or image from it won't appear. Stylesheets from it load for readers but are missing in the PDF |
| Page viewer | `grep -c 'attachShadow'` | 0 → no page viewer, so `freePages` is ignored and the form falls at the first block. Tell the person |
| Title | `grep -oiE '<title>[^<]{0,200}</title>'` | Use it to suggest `title`; warn if missing |
| Headings | `grep -oiE '<h[1-3][^>]{0,80}>[^<]{1,120}' \| head -20` | Use for the excerpt and SEO suggestions |
| Fonts | `grep -oiE "font-family:[^;\"]{1,80}" \| sort \| uniq -c \| head` | Advisory: not DM Sans or Inter |
| Brand colours | `grep -oiE '#(000523\|c6e1ee\|f7f5f0)' \| sort \| uniq -c` | Advisory: none of the brand colours used |

Ask the person for `freePages` (default 1). With a page viewer, it must leave at least
the last page locked.

## 3. Check rich text (`bodyFormat: "rich"`)

- Convert the content to Portable Text as `reference.md` describes: allowed styles,
  lists, marks and links only, every item with a `_key`.
- Turn `h1` into the `title` (or `h2` if a title already exists). Turn tables into
  lists. Note every image the person must add in the Studio.
- Ask for `lockedPercent` (10–90, default 75).

## 4. Fields and slug

Propose `title`, `slug`, `excerpt`, `seoTitle` (≤ 60), `seoDescription` (≤ 155), `silo`,
and an optional `cta`. Ask whether to pin the home banner (default no).

Check the slug is free:

```groq
count(*[_type == "report" && slug.current == $slug])
```

It must be `0` (the count covers drafts too). If it's taken, propose another.

Write to `<dir>`:

- `fields.json`: the full document content you'll send, minus `html`.
- `checks.md`: each check above, its result, and anything the person must do by hand
  (paste HTML, add the cover, add images).

Show the person `checks.md` and the fields, and wait for an OK before writing.

## 5. Write the draft

Create one `report` document with the Sanity MCP's **create documents** tool:
`projectId: itidwo8t`, `dataset: production`, content from `fields.json`. Always include
`bodyFormat`, `publishedAt` and `bannerPinned`.

- **Rich:** include `body`. If the JSON is near 100 KB, create without `body`, then add
  it with **patch documents**: `setIfMissing: {"body": []}`, then
  `insert: {after: "body[-1]", items: [...]}` in batches under 90 KB.
- **HTML, 60 KB or less:** include `html`, read in full from `report.html`, unchanged.
  Then confirm it arrived intact:

  ```groq
  *[_id == $draftId]{"len": length(html)}
  ```

  (`$draftId` is the `drafts.…` id from the create result) against `wc -m report.html`. If they differ by more than a few characters, tell the
  person to paste the file into **Report HTML** in the Studio instead.
- **HTML over 60 KB:** create without `html`. Tell the person: open the Studio link,
  open `<dir>/report.html` in a text editor, select all, copy, and paste into
  **Report HTML**.

## 6. Hand off

Never publish. Give the person:

1. The Studio link (see `reference.md`), with the id from the create result minus
   `drafts.`.
2. What's left for them: paste HTML (if needed), add the cover image (without one, the
   Webflow card and share image are blank), then **Publish**.
3. An offer: once published, you can check where the form gate landed:

   ```groq
   *[_id == $id]{renderedPreviewEnd, "renderedLen": length(renderedHtml)}
   ```

   with `$id` the published id (no `drafts.`).

   `renderedPreviewEnd` is the character offset in `renderedHtml` where the free
   preview ends. Compare it with `renderedLen`: a very small share means the gate fell
   at the first block.
