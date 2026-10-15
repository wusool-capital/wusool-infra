# Reference: what Sanity stores and the site renders

Source of truth: `sanity/schemaTypes/*.ts` and `server/app/modules/lead_magnets/` in
`wusool-infra`. If a check here disagrees with the live schema (the Sanity connector's
**get schema** tool), trust the schema and tell the person.

Project `itidwo8t`, dataset `production`, Studio `https://wusool-reports.sanity.studio`.

## Tools

Claude chat (or Cowork) with the **Sanity connector** and the **code tool** turned on.
In Claude Code, the code tool is the shell.

| Job | Tool |
|---|---|
| Read | Sanity **query documents**. Responses cap near 64 KB: project only the fields you need, and use `length(field)` for large text |
| Write fields | Sanity **create documents** / **patch documents**. Each call must be under 100 KB of JSON. Both save drafts only |
| Files: cover, body images, report HTML | Sanity **upload from file**, then a POST from the code tool |
| Publish | Sanity **publish documents**, only with the person's approval (see Publish) |
| Checks on an attached file | The code tool (shell or Python). Never paste a large file into the conversation |

Never delete or unpublish anything.

### Upload a file

One upload per file; the file never goes into the conversation.

1. Call **upload from file**: `projectId: itidwo8t`, `dataset: production`, `assetType`
   `image` (cover, body images) or `file` (report HTML), and the `filename`.
2. In the code tool, POST the file's raw bytes to the returned `uploadUrl`, with its
   `Content-Type` and no auth header, JSON, base64 or multipart wrapping:

   ```python
   import urllib.request
   req = urllib.request.Request(UPLOAD_URL, data=open(PATH, "rb").read(), method="POST",
                                headers={"Content-Type": "text/html"})
   print(urllib.request.urlopen(req).read().decode())
   ```

3. The response's `reference` is the field value, as is: `cover`, a rich-text image
   block (add `_key` and `alt`), or the report's `htmlFile`.
4. A `403` saying `blocked-by-allowlist` or `Host not in allowlist` means the code tool
   can't reach Sanity. Tell the person uploads are blocked: a Claude org owner must add `mcp.sanity.io` under
   **Organization settings → Capabilities → Code execution → Additional allowed domains**,
   then start a new chat. An upload URL expires; prepare a new one if it did.

### Create a draft

1. Call **create documents** with the `type` and every field inside `content`. Leave out
   `_id`: Sanity generates it. Note the returned `drafts.<id>`.
2. If the JSON nears 100 KB (a long rich-text body), create without `body`, then
   **patch documents** on the draft: `setIfMissing: {"body": []}`, then
   `insert: {after: "body[-1]", items: [...]}` in batches under 90 KB.
3. Later changes in the same run: **patch documents** on the draft id (`set`, `unset`).

### Publish

Only when the person approves this document, every time:

1. Show them: title and live URL (`wusoolcapital.com/reports/<slug>` or
   `wusoolcapital.com/insights/<slug>`), and, if `bannerPinned` or `featured` is true,
   which item it unpins (query the currently pinned one).
2. Publish only after they reply "publish" or clearly approve. Approval covers this one
   document; a later edit needs a new approval.
3. Call Sanity **publish documents** with `ids: [{"id": "<uuid>"}]`: the
   id without `drafts.`. It publishes that document's current draft.
4. Confirm it went live, as the sub-skill describes.

### Fields to set yourself

The Studio's `initialValue`s don't apply. Always set these yourself:

  | Type | Field | Value |
  |---|---|---|
  | both | `bodyFormat` | `"rich"` or `"html"`. Unset reads as HTML on the server. |
  | both | `publishedAt` | The person's date, else the current time in UTC, as ISO 8601, from the code tool (`date -u +%Y-%m-%dT%H:%M:%SZ`). Never a fixed or example time |
  | report | `bannerPinned` | `false`, unless the person asks to pin it |
  | insights | `contentType` | `"Article"` unless told otherwise |
  | insights | `featured` | `false`, unless the person asks to pin it |

- Never write `renderedHtml`, `renderedPreviewEnd` or `renderedFrom`; the server owns them.
- Never touch report `6ea065ae-fae1-4c7e-a3ec-6d67304ccc17` or its draft.

## Staff fields

The **content** comes from what the person gives: the attached HTML, document, Markdown
or pasted text (`body` / `bodyHtml` / `htmlFile`, plus `keyTakeaways` and `faq` if the
source has those sections). **Every other field is a staff field.**

Rules for staff fields:

- Ask for all of them in one message, as one table with three columns: field (Studio
  label), your suggestion, and what blank means (a few words, from the tables below).
  No other explanation.
- You may suggest a value from the content (marked "suggested"), but only the person's
  answer or an explicit "use your suggestions" fills a field. Never invent a value.
- Under the table, one line: "Still blank: X, Y, Z. Leave these blank?" Wait for an
  explicit OK. Required ones can't be left blank.
- After writing, end with one line listing the fields left blank.

### Insights staff fields (Studio order)

| Field | Required | If left blank |
|---|---|---|
| Title | Yes | — |
| Slug | Yes | — (suggest from the title) |
| Content type | Yes | — (Article, Playbook, Case Study or Press) |
| Excerpt | Yes | — (the /insights card and search results) |
| Cover image | No | The card keeps the site's default picture |
| Author | No | No author on the article |
| Primary silo | No | No silo tag |
| Published date | No | Now |
| Pin to top of /insights | No | Not pinned |
| H1 | No | The title |
| SEO title | No | The title |
| SEO description | No | The excerpt |
| Share title | No | The title |
| Target keyword | No | None |
| End-of-page button (text + link) | No | No button. Insight + report fills it automatically |
| Insight + report? | Ask always | Not linked to a report |

### Reports staff fields (Studio order)

| Field | Required | If left blank |
|---|---|---|
| Title | Yes | — |
| Slug | Yes | — (suggest from the title) |
| Excerpt | No | The /reports card has no description |
| SEO title | No | The title |
| SEO description | No | The excerpt, else the title |
| Share title | No | The title |
| Free pages (HTML) / Locked share % (rich) | No | 1 page / 75% locked |
| Cover image | No | The card keeps the site's default picture |
| Primary silo | No | No silo tag |
| Published date | No | Now |
| Pin to home page banner | No | Not pinned |
| End-of-page button (text + link) | No | No button |

## Fields

### `report`

| Field | Type | Rule |
|---|---|---|
| `title` | string | Required, max 256 |
| `slug` | `{_type:"slug", current}` | Required, `^[a-z0-9-]+$`, max 96, unique among reports |
| `excerpt` | text | Optional, 2–3 sentences |
| `seoTitle` | string | Max 60 |
| `seoDescription` | text | Max 155 |
| `ogTitle` | string | Optional |
| `bodyFormat` | `"rich"` \| `"html"` | Always set |
| `body` | rich text | Required when `rich` |
| `htmlFile` | file | The exported page as an uploaded `.html` file. Use this for HTML reports |
| `html` | text | The same page pasted as text. Exactly one of `html` and `htmlFile`; leave `html` unset |
| `freePages` | integer ≥ 1 | HTML only. Blank = 1; the last page always stays locked |
| `lockedPercent` | integer 10–90 | Rich only. Blank = 75 |
| `cover` | image | Uploaded (see Upload a file). Without one, the Webflow card and share image are blank |
| `silo` | enum | See below |
| `publishedAt` | datetime | Always set |
| `bannerPinned` | boolean | Pinning moves the home banner from the current report |
| `cta` | `{text, url}` | Both or neither. `text` max 80; `url` is full or a site path like `/sell` |

### `insights`

| Field | Type | Rule |
|---|---|---|
| `title` | string | Required, max 256 |
| `slug` | `{_type:"slug", current}` | Required, `^[a-z0-9-]+$`, max 96, unique in Sanity insights **and** Webflow Insights |
| `contentType` | enum | Required: `Article`, `Playbook`, `Case Study`, `Press` |
| `excerpt` | text | Required, 2–3 sentences |
| `bodyFormat` | `"rich"` \| `"html"` | Always set; applies to body, key takeaways and FAQ |
| `body` / `bodyHtml` | rich text / text | Required (whichever `bodyFormat` picks) |
| `keyTakeaways` / `keyTakeawaysHtml` | rich text / text | Optional |
| `faq` / `faqHtml` | rich text / text | Optional |
| `cover` | image | Uploaded (see Upload a file). Without one, the Webflow card and share image are blank |
| `author` | enum | `Jules Chasles`, `Hugo Cugnet`, `Ramzy Osman`, `Maria Najjar`, `Wusool Capital` |
| `silo` | enum | See below |
| `publishedAt` | datetime | Always set |
| `featured` | boolean | Pins to the top of /insights, unpinning the current one (hand-written included) |
| `h1` | string | Optional keyword heading; blank uses the title |
| `seoTitle` | string | Max 60 |
| `seoDescription` | text | Max 155 |
| `ogTitle` | string | Optional |
| `targetKeyword` | string | Optional |
| `cta` | `{text, url}` | Both or neither. `text` max 80 |

### `silo` values (exact spelling)

`Sell Your Business`, `Business Valuation`, `Exit Strategy`, `Buy a Business`,
`GCC M&A Market`, `General`, `Entrepreneurship Through Acquisition (ETA) GCC`.

There are no author, category or link document types.

## Rich text (Portable Text)

Allowed, and nothing else:

- **Styles:** `normal`, `h2`, `h3`, `h4`, `h5`, `h6`, `blockquote`. No `h1`.
- **Lists:** `listItem: "bullet"` or `"number"`, with `level` (1 = top).
- **Decorators:** `strong`, `em`, `underline`, `strike-through`, `code`, `sup`, `sub`.
- **Annotation:** `link` with `href` (full URL, site path, or `mailto:`) and optional `blank`.
- **Image block:** `{_type:"image", _key, asset:{_type:"reference", _ref:"image-…"}, alt}`.
  Ask the person to attach each image, upload it, and always set `alt`.
- **Not possible:** tables, embeds, iframes, code blocks, colours, fonts. Turn tables into
  lists or short paragraphs, and say so in `checks.md`.

Every array item needs a unique `_key` (8–12 random lowercase letters and digits).
Shape:

```json
{"_type":"block","_key":"a1b2c3d4","style":"normal","markDefs":[
  {"_type":"link","_key":"l1k2e3y4","href":"/reports/some-slug"}],
 "children":[
  {"_type":"span","_key":"s1p2a3n4","text":"Read the ","marks":[]},
  {"_type":"span","_key":"s5p6a7n8","text":"full report","marks":["l1k2e3y4","strong"]}]}
```

A list item is the same block plus `"listItem":"bullet","level":1`.

## Pasted HTML (insights `*Html` fields)

On publish the server keeps only these tags: `p h2 h3 h4 h5 h6 blockquote strong em u s
code sup sub ul ol li a br figure img figcaption`. Only `a[href,target]` and
`img[src,alt]` keep attributes. Tables, `div`/`span` wrappers, `script`, `style`, `class`,
and inline styles are all removed.

## Report HTML (the `html` field)

The server opens the HTML in a locked-down headless Chromium, waits for it to settle,
then saves a static snapshot:

- **No network while rendering.** Scripts, images and data must be inline. External
  stylesheets stay as `<link>` for readers' browsers, but the PDF download loads only
  `fonts.googleapis.com`, `fonts.gstatic.com` and `cdn.sanity.io`.
- **`<meta http-equiv="refresh">` is stripped**: the page must not depend on it.
- **Scripts, iframes, embeds and event handlers are removed** from the snapshot, so
  anything visible must be drawn by the time the page settles (8 s max, 30 s overall).
- **Free pages:** `freePages` only works when the page has a page viewer: an element
  with a shadow root and more than one child (each child is a page). Without one, the
  form gate falls at the first block, whatever `freePages` says.
- `<template>`, `<noscript>` and `[hidden]` content is removed.

## Brand (advisory, never blocking)

From `server/app/modules/lead_magnets/static/*/00-styles.css`:

| Token | Value |
|---|---|
| Navy | `#000523` |
| Sky | `#C6E1EE` |
| Paper | `#F7F5F0` |
| Fonts | DM Sans, Inter |

`#336a85` (darkened Gulf Blue) is the docs-diagram accent, not a site colour.

## Sync to Webflow

- Only **published** documents sync; drafts never do.
- Clearing a field in Sanity doesn't clear it in Webflow; clear it there too.
- An insight whose slug a hand-written Webflow article already uses is **silently
  skipped**.
- Webflow collections: Reports `6ac64c92647fc1acb46497de`, Insights
  `69aaa645fa60624091050e8e`.

## Studio link (optional)

For a person who wants to look before publishing:
`https://wusool-reports.sanity.studio/intent/edit/id=<id>;type=<report|insights>`, where
`<id>` is the document id **without** the `drafts.` prefix.
