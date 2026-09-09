# static

The four tool pages, `embed.js`, and their extracted images.

**Empty on purpose.** The pages live in `dopamine-relay` /
`wusool-benchmark` (private, on a personal GitHub account) and have to be
imported before this directory can be filled — see the module README's
"Blocked on" section.

When they land, they belong here as:

```
valuation.html  readiness.html  benchmark.html  buyers.html
embed.js
img/<sha8>.<ext>
```

Three things the import has to do, not just a copy:

- **Extract the inline base64 images** to `img/<sha8>.<ext>` and rewrite each
  `src`. That is ~212KB of the valuation page's 564KB, and content-addressed
  names are what make the year-long `Cache-Control` in `api/static.py`
  safe. Commit the rewritten HTML only, never both forms.
- **Repoint every AI call** at `/api/tools/*` with a relative path. The pages
  currently compose the prompts themselves and post them to a pass-through
  endpoint; afterwards they send data and receive validated JSON. Relative
  paths are what make the calls same-origin, which is why no CORS
  middleware exists.
- **Emit height.** None of the three pages tells its parent how tall it is
  today, which is why the current embeds are a fixed height. A
  `ResizeObserver` posting `{type: "wusool:height", id, height}` to
  `parent` is all `embed.js` needs.

Everything under here is served by `ToolStatic`, which sets the CSP
`frame-ancestors` and the two-tier cache policy. `embed.js` is deliberately
short-cached: it is both the cutover switch and the rollback switch.

`embed.js` must use the **full filename** — `/valuation.html`, not
`/valuation`. Starlette's `html=True` serves `index.html` for a directory
path; it does not strip extensions the way nginx does. Covered by
`tests/unit/test_static_headers.py` so it is not rediscovered against a
production 404.

One hazard when wiring the mount: `StaticFiles` raises
`RuntimeError: Directory ... does not exist` unless `check_dir=False`, and
this directory is empty until the pages land (`.dockerignore` excludes
`**/*.md`, so even this file is absent from the image). Do not add the mount
to `server/main.py` before there is a real file here.

Why this directory and not a top-level one: `_deploy.yml`'s toolkit change
detection matches `^server/`, and `pyproject.toml`'s hatchling
`packages = ["app"]` ships every non-Python file under `app/` into the
wheel — so files here deploy with no CI or Dockerfile change.
