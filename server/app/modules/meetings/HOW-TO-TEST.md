# How to test `meetings`

## Fast checks (no database, no AWS/Attio creds)

From `server/`:

```bash
uv run ruff check app/modules/meetings/
uv run ruff format --check app/modules/meetings/
uv run ty check app/modules/meetings/
uv run pytest app/modules/meetings/tests/test_architecture.py tests/test_architecture.py -q
```

The architecture test is the load-bearing one: it fails the build if
`domain/`/`application/` import `pydantic`/`sqlalchemy`/`fastapi` or this
module's own `persistence/`/`providers/`/`api/`. Run it after every change
to those two layers, not just before a PR.

**Current coverage note:** only `test_architecture.py` exists today.
`tests/unit/` and `tests/integration/` are scaffolded (package markers only)
but empty — write unit tests there as you touch a layer (see "What to cover
next" below) rather than assuming behavior is already pinned.

## Full repo checks

```bash
cd server
./checks.sh quality       # ruff check, ruff format --check, ty — whole repo
./checks.sh unit          # every module's tests, repo-wide fitness tests
./checks.sh schema        # requires CHECKS_DATABASE_URL — alembic upgrade head + alembic check
```

`./checks.sh unit` also re-runs `matching_engine`'s
`tests/unit/test_meeting_note.py` and
`tests/integration/test_meeting_repository.py` — those are this module's
regression guard for the shared `meetings` table: if a change here breaks
the rendered-`summary`/`org_id` contract `matching_engine` reads, those
tests catch it, not this module's own suite.

## Manual end-to-end smoke test

Requires a real (or local Docker) Postgres with this repo's migrations
applied, and `DESKTOP_API_KEY` set (see `.env.example`'s "meetings module
only" section). AWS/Attio creds are optional — omitting
`ATTIO_NOTE_OBJECT_SLUG` and AWS keys still runs the full flow (Bedrock
falls back to the default credential chain; a missing/invalid one surfaces
as a `BedrockInvocationError` → the meeting ends up `status=failed` rather
than the request failing).

```bash
uv run python main.py   # from server/, or docker compose up

# Push a short transcript
curl -s -X POST http://localhost:8000/desktop/meetings \
  -H "Authorization: Bearer $DESKTOP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "install_id": "smoke-test",
    "local_recording_id": "smoke-test-1",
    "transcript": [
      {"speaker": "Participant", "start": 0.0, "end": 5.0,
       "text": "Thanks for joining. Let'"'"'s go over the Q3 roadmap and confirm next steps."}
    ],
    "duration_seconds": 300
  }'
# -> 201 {"meeting_id": "...", "status": "summarizing", "already_existed": false}

# Poll (repeat until status is "completed" or "failed")
curl -s http://localhost:8000/desktop/meetings/<meeting_id> \
  -H "Authorization: Bearer $DESKTOP_API_KEY"

# Re-push the same (install_id, local_recording_id) -> expect 409
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/desktop/meetings \
  -H "Authorization: Bearer $DESKTOP_API_KEY" -H "Content-Type: application/json" \
  -d '{"install_id":"smoke-test","local_recording_id":"smoke-test-1","transcript":[],"duration_seconds":1}'

# Wrong/missing key -> expect 401
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/desktop/meetings/<meeting_id>
```

Then check Postgres directly: `meetings.summary` should be non-empty
rendered text, `meetings.summary_json` a well-shaped object, and (if
`org_id` resolved) a matching row in `notes`.

## What to cover next

Priority order if you're adding tests rather than just running the existing
ones:

1. `providers/bedrock/client.py` — forced-tool-call request shape,
   `_extract_json`'s fallback ladder, transient-error retry via
   `retry_with_backoff`, non-transient fail-closed.
2. `application/summarize.py` — the `_MIN_TRANSCRIPT_WORDS` short-circuit,
   single-pass vs. map/reduce chunking boundary, uniform `max_tokens`.
3. `application/ingest.py` — role precedence (seller > buyer > investor >
   internal > general), the `attio:<id>` / `__create_new__` / bare-UUID
   selection paths, dedupe → `MeetingAlreadyExistsError`.
4. `persistence/meetings_repository.py::recover_stalled` — the conditional
   UPDATE is the concurrency lock; a test firing it twice concurrently for
   the same stalled row should see exactly one `True`.
5. `api/` routes — auth rejection (missing/wrong key), the transcript
   size cap returning 422 before `ingest_meeting` is ever called.
