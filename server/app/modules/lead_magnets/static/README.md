# static

The four tool pages, `embed.js`, and their extracted images.

**Landing tool by tool.** Benchmark and readiness are in — both split into
`00-styles.css` plus numbered `.js` files at legal boundaries (benchmark:
its own `/* SECTION */` comments; readiness: one file per function group,
since it had no such comments), one embedded image each extracted to
`img/`, and their submit calls repointed at `/benchmark` and
`/readiness/score` directly instead of the old Render relays. Readiness's
repoint is bigger than a URL swap: the server now builds the prompt, scores
it, and records the lead in one call, so the page no longer composes its
own Claude prompt (`buildPrompt`/`callClaude`) or separately pushes to
Attio (`buildAdvisoryContent`/`pushReadinessToAttio`/
`revenueRangeToMidpointUsd`) — all four deleted, all ported server-side
already in `domain/readiness/readiness.py`. Valuation and buyers are still
not here.

```
valuation/  buyers/                             # not built yet
benchmark/
  index.html
  00-styles.css
  10-config.js  20-data.js  30-helpers.js  40-scoring.js  50-narrative.js  60-render.js
readiness/
  index.html
  00-styles.css
  10-state.js  20-nav.js  30-submit.js  40-results.js
embed.js
img/<sha8>.<ext>       # shared across tools — logo dedupes by content hash
shared/height.js        # ResizeObserver -> parent.postMessage, every tool includes it
```

Every `<script src>`/`<link href>` carries a hand-bumped `?v=1` cache-buster
(bump on any content change to that file — `.js`/`.css` are `max-age=60`,
so without it a deploy has a 60-second window where old JS can pair with
new HTML). Every `<script src>` also carries `onerror="window.__lmFail=1"`,
checked by one final inline `<script>` against a per-page sentinel
(benchmark: `typeof render === "function"`) — a failed fetch or a mid-file
parse error otherwise leaves the page silently half-working rather than
visibly broken. `tests/unit/test_static_contract.py` and
`tests/unit/test_embed_js.py` pin the parts of this that are mechanically
checkable: every ref resolves to a real file, no page still carries a
base64 image, and the outbound payload field names match the request
schema.

Each tool is fully self-contained under its own folder, `index.html` included — the
same grouping this module's Python layers already use
(`domain/valuation/`, `application/valuation/`, `api/valuation/`). `img/` and `shared/`
sit as siblings at `static/` root because they're used by more than one tool; nothing
single-tool belongs there.

Three things the import has to do, not just a copy:

- **Extract the inline base64 images** to `img/<sha8>.<ext>` and rewrite each
  `src`. That is ~212KB of the valuation page's 564KB, and content-addressed
  names are what make the year-long `Cache-Control` in `api/static.py`
  safe. Commit the rewritten HTML only, never both forms.
- **Repoint every call** at the real endpoint with a relative, same-origin
  path (the router has no `/api/tools` prefix — `POST /benchmark` etc. are
  the paths the pages already know). Field names have to match the request
  schema exactly (`api/schemas.py` is `extra="forbid"`, snake_case), which
  for benchmark and readiness meant rebuilding the payload rather than just
  swapping the URL — see each tool's `30-submit.js`/render script. Valuation
  still composes its own AI prompts and posts them to a pass-through
  endpoint; that call needs to send data and receive validated JSON instead.
- **Emit height.** `shared/height.js` posts `{type: "wusool:height", height}`
  to `parent` on a `ResizeObserver`; every tool's `index.html` includes it
  as its last script. `embed.js` disambiguates which iframe a message came
  from via `event.source === iframe.contentWindow`, not a shared id — the
  child has no way to learn an id the parent assigns after creating the
  iframe, so an earlier draft that required one silently never matched and
  every embed stayed pinned at `fallbackHeight` forever. Caught before any
  tool used it.

Everything under here is served by `ToolStatic`, which sets the CSP
`frame-ancestors` and the two-tier cache policy. `embed.js` is deliberately
short-cached: it is both the cutover switch and the rollback switch.

`embed.js` must use the **trailing-slash directory form** — `/valuation/`,
not `/valuation`. Starlette's `html=True` serves `index.html` for a
directory path (`/valuation/` → 200), but a bare `/valuation` costs a 307
redirect to `/valuation/` first — same headers, one avoidable round trip.
Verified against this repo's pinned Starlette (1.6.0): the redirect
response itself still carries the CSP and cache headers, so nothing breaks
if `embed.js` gets this wrong, it's just slower. Covered by
`tests/unit/test_static_headers.py` so the redirect cost isn't
rediscovered as a production latency mystery.

The mount is wired: `server/main.py` mounts `ToolStatic(directory=static_dir(), html=True)`
at `/`, last, after every router — verified live and via a real `podman build`
image inspection that the wheel actually ships this directory
(`.dockerignore` excludes `**/*.md`, so only the non-`.md` files here reach
the image).

Why this directory and not a top-level one: `_deploy.yml`'s toolkit change
detection matches `^server/`, and `pyproject.toml`'s hatchling
`packages = ["app"]` ships every non-Python file under `app/` into the
wheel — so files here deploy with no CI or Dockerfile change.
