param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [ValidateRange(1, 16)]
  [int]$Workers = 8,
  [switch]$Apply
)

# One-time backfill of prod Postgres's `meetings` table from SOURCE Attio's
# native per-record Notes on Companies/People -- the same Granola-classified
# "Meeting" notes backfill-notes.ps1 already detects (granola.ai link or
# "Chat with meeting transcript" phrase), but written here into `meetings`
# instead of `notes`. meeting.py's own docstring anticipates exactly this:
# "Owned and written by Scribe... and by the one-time Attio notes migration."
#
# HONEST LIMITS -- what SOURCE Attio actually has vs. doesn't:
#   - summary: YES -- the Granola summary text is the note's own content,
#     same cleanup as backfill-notes.ps1's Format-NoteContent (strip the
#     "---\nChat with meeting transcript:" footer, keep title if not
#     redundant).
#   - created_by_ref: YES -- parsed from the note's own "Added by: X" line
#     (also stripped from the stored summary, same as backfill-notes.ps1).
#   - occurred_at (NOT NULL column): PROXIED, not exact -- Attio has no
#     separate "meeting happened at" field on a native note, only its own
#     system created_at (when Granola pushed the note). Used as the closest
#     available stand-in.
#   - metadata.granola_transcript_url: YES -- the notes.granola.ai link
#     itself, for whoever wants to open the real transcript later.
#   - transcript, participants, duration_s, audio_ref: NO -- none of these
#     exist anywhere in the SOURCE Attio note. Left NULL, not guessed.
#   - counterparty_role, meeting_type: NO -- Scribe's own categorization
#     scheme, no equivalent signal in an Attio note. Left NULL.
#   - source: always 'granola' -- every note this script picks up was
#     already classified as Meeting via the granola.ai/transcript signal.
#
# Idempotent: `meetings.id` reuses the native Attio note's own note_id
# (already a UUID) verbatim, same pattern as sync-notes-from-source.ps1
# reusing the `note` object's own id -- upserts are ON CONFLICT(id).
#
# Org resolution is one hop, same as backfill-activities.ps1: native
# Company/Person id -> SOURCE custom organizations/person's own
# legacy_attio_id -> that custom object's record id (which prod Postgres's
# organizations.attio_id already equals directly). A note on a Person whose
# company can't be resolved gets org_id left NULL and org_name_raw set
# instead (meeting.py's own documented fallback for this exact case).

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ($Apply -and [string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }

$env:WUSOOL_SOURCE_ATTIO_API_KEY = $SourceApiKey.Trim()
$env:WUSOOL_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_APPLY = if ($Apply) { "1" } else { "0" }
$env:WUSOOL_WORKERS = "$Workers"

try {
@'
import json, os, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

APPLY = os.environ.get("WUSOOL_APPLY") == "1"
KEY = os.environ["WUSOOL_SOURCE_ATTIO_API_KEY"]
WORKERS = int(os.environ.get("WUSOOL_WORKERS", "8"))
BASE = "https://api.attio.com/v2"
HEADERS = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "Content-Type": "application/json"}

def request(method, path, body=None):
    payload = None if body is None else json.dumps(body).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(BASE + path, data=payload, headers=HEADERS, method=method)
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500: raise
            if attempt == 7: raise
            time.sleep(min(90, 15 * (attempt + 1)))

def pages_object(slug):
    result, offset = [], 0
    while True:
        batch = request("POST", f"/objects/{slug}/records/query", {"limit": 500, "offset": offset}).get("data", [])
        result.extend(batch)
        if len(batch) < 500: return result
        offset += 500

def items(v, slug): return [x for x in (v.get(slug) or []) if x.get("active_until") is None]
def first(v, slug):
    xs = items(v, slug)
    if not xs: return None
    x = xs[0]
    for path in (("value",), ("option", "title"), ("status", "title")):
        cur = x
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is not None: return cur
    return None
def ref(v, slug):
    xs = items(v, slug)
    return xs[0].get("target_record_id") if xs else None
def record_id(r): return str((r.get("id") or {}).get("record_id") or "")

print("Reading SOURCE custom organizations/person (legacy_attio_id crosswalk + person->company)...")
custom_orgs = pages_object("organizations")
custom_people = pages_object("person")

org_by_legacy = {}
for r in custom_orgs:
    legacy = first(r.get("values") or {}, "legacy_attio_id")
    if legacy: org_by_legacy[str(legacy)] = record_id(r)

person_by_legacy = {}
person_org = {}
for r in custom_people:
    v = r.get("values") or {}
    legacy = first(v, "legacy_attio_id")
    pid = record_id(r)
    if legacy: person_by_legacy[str(legacy)] = pid
    company = ref(v, "company")
    if company: person_org[pid] = company

print(f"Organizations: {len(custom_orgs)} ({len(org_by_legacy)} bridgeable). Person: {len(custom_people)} ({len(person_by_legacy)} bridgeable, {len(person_org)} with a company).")

print("Reading SOURCE native Companies/People...")
native_companies = pages_object("companies")
native_people = pages_object("people")

def get_native_notes(parent_object, native_id):
    result, offset = [], 0
    while True:
        page = request("GET", f"/notes?parent_object={parent_object}&parent_record_id={native_id}&limit=50&offset={offset}").get("data", [])
        result.extend(page)
        if len(page) < 50: return result
        offset += 50

def raw_body(note):
    return note.get("content_plaintext") or note.get("content_markdown") or ""

_GRANOLA_RE = re.compile(r"(?i)granola\.ai|chat with meeting transcript")
_FOOTER_RE = re.compile(r"(?is)\r?\n-{3,}\s*\r?\nChat with meeting transcript:.*$")
_ADDED_BY_RE = re.compile(r"(?im)^Added by:\s*(.+)$")
_ADDED_BY_STRIP_RE = re.compile(r"(?im)^Added by:.*\r?\n?")
_GRANOLA_LINK_RE = re.compile(r"(https?://notes\.granola\.ai\S*)")

def is_meeting(note): return bool(_GRANOLA_RE.search(raw_body(note)))

def clean_summary_and_author(note):
    body = raw_body(note)
    body = _FOOTER_RE.sub("", body)
    match = _ADDED_BY_RE.search(body)
    created_by = match.group(1).strip() if match else None
    body = _ADDED_BY_STRIP_RE.sub("", body).strip()
    title = note.get("title") or ""
    if title and not body.startswith(title):
        body = f"# {title}\n\n{body}" if body else title
    return body, created_by

def granola_link(note):
    match = _GRANOLA_LINK_RE.search(raw_body(note))
    return match.group(1) if match else None

def process_company(c):
    v = c.get("values") or {}
    native_id = record_id(c)
    org_id = org_by_legacy.get(native_id)
    fallback_name = first(v, "name")
    rows = []
    for n in get_native_notes("companies", native_id):
        if not is_meeting(n): continue
        summary, created_by = clean_summary_and_author(n)
        link = granola_link(n)
        rows.append({
            "id": str((n.get("id") or {}).get("note_id") or ""),
            "org_id": org_id, "org_name_raw": None if org_id else fallback_name,
            "occurred_at": n.get("created_at"), "title": n.get("title"),
            "summary": summary, "created_by_ref": created_by,
            "metadata": {"granola_transcript_url": link} if link else {},
        })
    return rows, (0 if org_id else 1)

def process_person(p):
    v = p.get("values") or {}
    native_id = record_id(p)
    custom_person_id = person_by_legacy.get(native_id)
    org_id = person_org.get(custom_person_id) if custom_person_id else None
    fallback_name = first(v, "name")
    rows = []
    for n in get_native_notes("people", native_id):
        if not is_meeting(n): continue
        summary, created_by = clean_summary_and_author(n)
        link = granola_link(n)
        rows.append({
            "id": str((n.get("id") or {}).get("note_id") or ""),
            "org_id": org_id, "org_name_raw": None if org_id else fallback_name,
            "occurred_at": n.get("created_at"), "title": n.get("title"),
            "summary": summary, "created_by_ref": created_by,
            "metadata": {"granola_transcript_url": link} if link else {},
        })
    return rows, 0

print(f"Scanning native notes on {len(native_companies)} companies + {len(native_people)} people for Meeting-classified notes (using {WORKERS} workers)...")
meeting_rows = []
companies_org_unresolved = 0
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    futures = [pool.submit(process_company, c) for c in native_companies] + [pool.submit(process_person, p) for p in native_people]
    done = 0
    for fut in as_completed(futures):
        rows, unresolved = fut.result()
        meeting_rows.extend(rows)
        companies_org_unresolved += unresolved
        done += 1
        if done % 500 == 0: print(f"  ...{done}/{len(futures)} scanned")

with_org = sum(1 for m in meeting_rows if m["org_id"])
print(f"Meeting-classified notes found: {len(meeting_rows)} -- ALL of them included, none dropped ({with_org} with a resolved org, {len(meeting_rows) - with_org} using org_name_raw fallback since their company isn't in organizations yet). Companies with org unresolved: {companies_org_unresolved}.")
for sample in meeting_rows[:5]:
    preview = (sample["summary"] or "")[:80]
    print(f"  SAMPLE: {sample['id']} org={sample['org_id']} title={sample['title']!r} summary=\"{preview}\"")

if not APPLY:
    print("DRY RUN complete. Add -Apply to write these rows.")
    sys.exit(0)

import psycopg
from psycopg.types.json import Jsonb
with psycopg.connect(os.environ["WUSOOL_DATABASE_URL"], connect_timeout=10) as conn:
    with conn.cursor() as c:
        c.execute("SELECT current_database()")
        if c.fetchone()[0] != "wusool_crm":
            raise RuntimeError("Refusing to write outside wusool_crm")
        rows = [(
            m["id"], m["org_id"], m["org_name_raw"], m["occurred_at"], m["title"],
            m["summary"], m["created_by_ref"], Jsonb(m["metadata"]),
        ) for m in meeting_rows]
        c.executemany(
            """INSERT INTO meetings(id, org_id, org_name_raw, occurred_at, title, source, summary, created_by_ref, metadata)
               VALUES(%s,%s,%s,%s,%s,'granola',%s,%s,%s)
               ON CONFLICT(id) DO UPDATE SET
                 org_id=excluded.org_id, org_name_raw=excluded.org_name_raw,
                 occurred_at=excluded.occurred_at, title=excluded.title,
                 summary=excluded.summary, created_by_ref=excluded.created_by_ref,
                 metadata=excluded.metadata""",
            rows,
        )
    conn.commit()
print(f"Upserted {len(meeting_rows)} meeting rows into PostgreSQL.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "Meetings sync from SOURCE failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_SOURCE_ATTIO_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_APPLY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_WORKERS -ErrorAction SilentlyContinue
}
