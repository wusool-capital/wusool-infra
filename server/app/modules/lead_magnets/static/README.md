# static

The four tool pages, `embed.js`, and their extracted images.

**All four tools are in.** Benchmark, readiness and valuation were ported
from live tools and repointed; buyers is genuinely new — the Buyer Network
never had a custom tool page, only a Tally form, so there was nothing to
port. Its 9 fields plus consent match `BuyerApplyRequest` exactly. Two of
its select fields (`org_type`, `sector_focus`) are a plain, searchable,
click-to-toggle widget of `<div class="ms-opt">` rows — no JS picker
library, no custom chip UI — rather than a native `<select multiple>`,
which needs ctrl/cmd+click to pick more than one option and isn't
discoverable in a public lead form. `target_geography` is single-select (a
plain `<select>`) — an applicant only ever targets one geography per
application — but the request/Attio field is still a list under the hood,
since Attio's own `target_geography` attribute is multiselect-typed; the
page just always sends a one-item list. Every option across all three
fields is generated from the same live Python option sets
(`domain/buyer_network/buyer_network.py`,
`domain/shared/sector_options.py`) rather than hand-typed, so there is
nothing to transcribe wrong. `test_buyers_select_options_match_the_live_validation_sets`
pins that the page and the domain module's option sets stay identical —
these fields aren't validated by the request schema (only the background
Attio write checks them), so a typo'd option here would otherwise record
the lead and then silently fail to land in the CRM.

Each split at legal boundaries — benchmark and valuation had their own
`/* SECTION */`-style comments to cut at; readiness and valuation's
`20-helpers.js`/`40-main.js` split had none, so those are one file per
function group instead. Valuation stays coarser than the other two per the
plan: `10-data.js` is ~180KB of pure data literals (`MA_RAW`, `VC_RAW`,
`PUBLIC_COMPS`, `DAMODARAN_WACC`, sector maps) as a **plain** `<script src>`
— no JSX, so transpiling it would be pure waste — while `20-helpers.js`,
`30-components.js` and `40-main.js` carry `type="text/babel"` like the
original monolith did. Splitting the ~180KB of React/JSX further than
that buys nothing and adds N more silent-Babel-failure surfaces for no
reason; see "Honest cost" in the migration plan.

Each tool's one embedded image is extracted to `img/`, and every AI/submit
call is repointed off the old Render relays (`dopamine-relay`,
`wusool-benchmark`) at this module's own endpoints. Valuation's repoint is
the biggest of the three: the live tool fired five independent client-
composed Claude calls across its lifecycle (enrich, a loading-screen
teaser, the full strategic read, the M&A readiness scorecard, and dynamic
comps); the backend consolidates these into three — `/enrich`, `/analyze`
(sector judgement, discounts, DCF overrides, the strategic read *and* the
readiness scorecard, merged), and `/compare` — fired from `App()`'s own
`useEffect`s instead of five separate component-level fetches. `pushLeadToAttio`,
`DynamicCompsLoader`, `callClaude`, `RELAY_BASE`, and the loading-screen
teaser's own abbreviated fetch are all deleted outright; `StrategicAnalysis`
and `FundraiseReadiness` become prop-driven (`analysis`/`fundraise`) instead
of firing their own requests, reading the one shared `/analyze` result.
`generateStrategicAnalysis` (the client's own deterministic port) survives
only as `LockedPreview`'s synchronous fallback while `/analyze` is still in
flight — everywhere else, `/analyze`'s own server-side fallback
(`domain/valuation/strategic_analysis.py`) already covers the failure case,
so nothing client-side needs to re-derive it.

Two fields the backend's `/analyze`/`/submit-lead` schemas accept but the
page deliberately never sends, both because there was never one unambiguous
client-side value to forward: `AnalyzeRequest.website_text` (the client-side
scraping that ever populated it was already dead in the live tool before
this migration) and `ValuationRequest.discounts` (`TradingComps` and
`TransactionComps` each keep their own independent discount sliders, not a
single shared one; the server already defaults to 50%/50% when absent, the
same as a sweeper resume with no model in reach). `test_static_contract.py`
pins both omissions explicitly, so a *third* field silently missing still
fails the test.

One simplification, noted rather than hidden: `StrategicAnalysis`'s
"AI-powered" badge and "Based on X's profile" vs. "Sector benchmarks"
copy used to reflect whether Claude's call actually succeeded. `/analyze`'s
response shape does not distinguish a Bedrock success from its own
deterministic fallback, so the client now always shows the AI-powered
copy. The fallback content is a verified byte-for-byte port of the live
tool's own local-fallback text, so this undersells a fallback response as
AI-generated in the rare case Bedrock fails — cosmetic, not a data
correctness issue.

Two dead-code findings bigger than the plan's own notes flagged, deleted
here rather than carried forward: the whole "WUSOOL CAPITAL NAV"/"FOOTER"
CSS block (59 lines — not just `footer-section`/`navbar-inner`, the *entire*
Webflow-exported nav/footer chrome, since the page never renders any
Webflow markup at all) had zero JSX usages of any class in it; and the one
inline image on `.footer-gradient-bg` was a 122.5KB JPEG mislabeled
`image/png`, on a class also never referenced in any JSX. Verified by grep
before deleting, not assumed from the plan's shorthand description of them.

```
benchmark/
  index.html
  00-styles.css
  10-config.js  20-data.js  30-helpers.js  40-scoring.js  50-narrative.js  60-render.js
readiness/
  index.html
  00-styles.css
  10-state.js  20-nav.js  30-submit.js  40-results.js
valuation/
  index.html
  00-styles.css
  10-data.js          # plain <script src>, no JSX
  20-helpers.js  30-components.js  40-main.js   # type="text/babel"
buyers/
  index.html
  00-styles.css
  10-main.js
embed.js
img/<sha8>.<ext>       # shared across tools — logo dedupes by content hash
shared/height.js        # ResizeObserver -> parent.postMessage, every tool includes it
```

Every `<script src>`/`<link href>` carries a hand-bumped `?v=1` cache-buster
(bump on any content change to that file — `.js`/`.css` are `max-age=60`,
so without it a deploy has a 60-second window where old JS can pair with
new HTML). Every `<script src>` also carries `onerror="window.__lmFail=1"`,
which a per-page sentinel checks to swap in a plain-text fallback message.
Benchmark, readiness and buyers check it in one final inline `<script>`
right after their `<script src>` tags (`typeof render === "function"` /
`typeof submitBuyerForm === "function"`); valuation cannot do that —
Babel's script loading is async, so a plain script placed immediately
after the `type="text/babel"` tags would run before Babel has even
fetched them, always finding nothing. Its check lives instead as the last
statement in `40-main.js` itself (also `type="text/babel"`, so it executes
in the correct order): a few seconds after the
`ReactDOM.createRoot(...).render()` call, if `#root` never got a child,
show `#lm-fallback`. This is also the one page-load failure mode `onerror`
genuinely cannot catch on its own — a bad slice that Babel fetches fine
(HTTP 200) but fails to *compile* throws inside the transpiler, never
firing `onerror` at all.
`tests/unit/test_static_contract.py` and
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
  `src`, and delete anything genuinely unused rather than extracting it —
  valuation's own logo image turned out to be byte-identical to readiness's
  (shared for free, `img/` gained no new file for it), and its one other
  image was a dead 122.5KB JPEG nothing ever referenced. Content-addressed
  names are what make the year-long `Cache-Control` in `api/static.py`
  safe. Commit the rewritten HTML only, never both forms. Valuation's total
  served weight (`index.html` + its 5 split files) is 327KB against the
  original single file's 564KB — the dead JPEG, the dead nav/footer CSS,
  and the deleted AI-prompt strings account for nearly all of the drop.
- **Repoint every call** at the real endpoint with a relative, same-origin
  path (the router has no `/api/tools` prefix — `POST /benchmark` etc. are
  the paths the pages already know). Field names have to match the request
  schema exactly (`api/schemas.py` is `extra="forbid"`, snake_case), which
  for benchmark, readiness and valuation meant rebuilding the payload
  rather than just swapping the URL — see each tool's `30-submit.js`/render
  script, or valuation's `App()` in `40-main.js` for the four-endpoint
  case. Buyers is a fresh page, so its `10-main.js` posts the right shape
  from the start (`POST /buyer/apply`, singular — the static page is
  plural `/buyers/`, so unlike the other three tools this was never even a
  near-collision).
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
