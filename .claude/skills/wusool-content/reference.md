# Reference: what Sanity stores and the site renders

Source of truth: `sanity/schemaTypes/*.ts` and `server/app/modules/lead_magnets/` in
`wusool-infra`. If a check here disagrees with the live schema (the Sanity MCP's
**get schema** tool), trust the schema and tell the person.

Project `itidwo8t`, dataset `production`, Studio `https://wusool-reports.sanity.studio`.

## MCP write rules

- Create and patch save **drafts only** (`drafts.<id>`). Publishing happens in the Studio.
- Each request must be under **100 KB** of JSON, including escaping.
- Query responses are capped near 64 KB: project only the fields you need, and use
  `length(field)` to check large text instead of reading it back.
- The Studio's `initialValue`s don't apply. Always set these yourself:

  | Type | Field | Value |
  |---|---|---|
  | both | `bodyFormat` | `"rich"` or `"html"`. Unset reads as HTML on the server. |
  | both | `publishedAt` | Today, as ISO 8601 (`2026-10-15T09:00:00.000Z`) |
  | report | `bannerPinned` | `false`, unless the person asks to pin it |
  | insights | `contentType` | `"Article"` unless told otherwise |
  | insights | `featured` | `false`, unless the person asks to pin it |

- Never write `renderedHtml`, `renderedPreviewEnd` or `renderedFrom`; the server owns them.
- Never touch report `6ea065ae-fae1-4c7e-a3ec-6d67304ccc17` or its draft.

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
| `html` | text | Required when `html`: the whole exported page |
| `freePages` | integer ≥ 1 | HTML only. Blank = 1; the last page always stays locked |
| `lockedPercent` | integer 10–90 | Rich only. Blank = 75 |
| `cover` | image | Added in the Studio |
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
| `cover` | image | Added in the Studio |
| `author` | enum | `Jules Chasles`, `Hugo Cugnet`, `Ramzy Osman`, `Maria Najjar` |
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
- **Image block:** `{_type:"image", asset:{_type:"reference", _ref:"image-…"}, alt}`. Needs
  an uploaded asset, so leave images to the person: list each one, with where it goes,
  in `checks.md`.
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
  skipped**. Webflow Insights collection: `69aaa645fa60624091050e8e`.
- With no cover image, the Webflow card and share image are blank.

## Studio link

`https://wusool-reports.sanity.studio/intent/edit/id=<id>;type=<report|insights>`, where
`<id>` is the document id **without** the `drafts.` prefix.
