# Web app and API

The [matching engine](toolkit-matching.md) also runs from a browser.

The web app (`client/`) runs the same flow in a browser. The Toolkit container
serves its build at `/app` (`SpaStatic`, which falls back to `index.html` for
deep links and caches hashed assets for a year) and its API under `/api`:

| Route | Does |
| --- | --- |
| `GET /api/buyers?q=` | Buyer search. |
| `POST /api/buyers/{id}/preflight` | Discrepancy check against the advisor's note. |
| `POST /api/match-runs` | Starts a run and returns 202 with its id. |
| `GET /api/match-runs/{id}` | Run state, candidates with reasoning, discovery progress. |
| `POST /api/match-runs/{id}/discovery` | Starts discovery by hand. |
| `POST /api/match-runs/{id}/candidates/{cid}/approve` | Approve, with the promote or create choice. |
| `POST /api/match-runs/{id}/candidates/{cid}/reject` | Reject. |
| `POST /api/match-runs/{id}/candidates/{cid}/research` | Starts or retries full research on an approved discovered seller (202). |
| `POST /api/match-runs/{id}/candidates/{cid}/research/save` | Writes the chosen proposed fields to the seller. Needs a Slack sign-in. |
| `POST /api/match-runs/{id}/candidates/{cid}/research/skip` | Closes the research without saving. |
| `GET /api/match-runs/{id}/export.csv` | The candidates as CSV, with formula characters neutralised. Repeat `fields` to choose and order columns; without it, all are exported. |

**Access.** People sign in with Slack (OpenID Connect, `openid profile`)
through `/api/auth/slack/login`. Only the workspace the Toolkit bot is
installed in is allowed. The callback sets a signed `HttpOnly` session cookie
for `WEB_SESSION_DAYS` (30), renewed by use. Once a day each session asks
Slack (`users.info`, bot scope `users:read`) whether the person is still
active. Runs record their Slack user ID as `requested_by`. Decisions record it
as `approved_by`, the same IDs Slack's `/find-match` writes. Cookie requests
that change data must send `X-Wusool-Client: web`. `Authorization: Bearer
<WEB_API_KEY>` still works as a fallback and records `web`. With neither set
up, every route returns 503.

**Runs.** The route commits the run's header row (`start_run`) and returns.
The matching itself (`execute_run`) runs on the shared in-process task runner,
as Slack's runs do. A run with no `completed_at` reads as running. After
`MATCH_RUN_STALE_AFTER_MINUTES` (default 15) it reads as stale: a deploy or
restart cut it off.

**Parity with Slack.** The run detail carries the requirement profile as
`mandate` and each scored candidate's `criteria`, the two parts of View Full
Analysis. Each candidate also carries `profile`, read from its organisation
and seller role. The profile check can't be skipped.

**Full research.** Approving a discovered seller claims its research on the
candidate row (`metadata.research`, no migration) and runs
`enrichment.propose_for_role` and `scan_linkedin_for_role` in the
background. That is the same research Slack posts, kept on the row instead
and shown in the page; nothing goes to Slack. The LinkedIn result is stored
the moment it lands, because a rescan returns only posts it hasn't seen. A
claim with no outcome past `MATCH_RUN_STALE_AFTER_MINUTES` reads as failed and
can be retried.

**Saving research.** `matching_engine` defines `SellerEditPort`;
`ddl_commands` implements it with the `/edit-seller` write
(`api/seller_edit.py`, Attio first, then Postgres), and `server/main.py`
wires it. The adapter validates with the edit form's models, only writes
fields that are still empty, and reports any filled in since as a conflict.
A save is claimed on the row (`saving_at`), so a double click writes once.
A save or a skip closes the review. The edit is recorded as `slack` under the
signed-in user, so the shared key can't save.

**One search per run.** Slack and the web claim a run's search outside the
CRM on the run row. A second click, a retry or a restart can't search
twice. The outcome and notes stay on the row, so the run page shows them
after a restart. A search that had nothing to search on, hit the daily cap or
failed releases its claim. It can then run again.

**Discovery.** Below `WEB_FALLBACK_MIN_SCORE`, a web run starts discovery
itself. Its progress and outcome counts live in an in-process tracker; after a
restart the page offers the manual start instead. The manual start is also
offered on runs that cleared the threshold.

**Settings.** The web settings are entries in the `env` map of the Toolkit
secret (`/wusool/<env>/toolkit`). A top-level key is ignored. Sign-in needs
`SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `WEB_SESSION_SECRET` and
`WEB_PUBLIC_URL`. `WEB_API_KEY` is optional. `WEB_ALLOWED_ORIGINS` (CORS)
stays empty while the app is served from the same host.

**Build and deploy.** The Toolkit image has a Node stage that builds
`client/`, passed in as a named build context (`--build-context
client=client` in `_build.yml`, `additional_contexts` in
`docker-compose.yml`). Changes under `client/**` trigger the deploy workflows.
The `Client quality` workflow checks types, lint, tests, the build, and that
the generated API client matches the server.
