param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply
)

# Populates PostgreSQL's `notes` table from SOURCE Attio's `note` custom
# object -- run after sync-source-to-prod.ps1 (organizations/person/
# buyer_roles/seller_roles must already exist for this to resolve anything).
#
# Simpler than ../dev-postgres-sync/sync-notes-from-source.ps1: that script
# bridges SOURCE record ids to Postgres via organizations.raw_attio's
# legacy_attio_id, because Postgres there is keyed by DEV Attio's own ids,
# one hop removed from SOURCE. Here, prod Postgres is synced directly from
# the same SOURCE custom objects the `note` object's organization_id/
# person_id record-references point at -- so those SOURCE record ids
# already ARE this Postgres's attio_id/id values. No bridging needed.
#
# buyer_role_id/seller_role_id on the note are the SOURCE list entry_id
# (plain text) -- matches buyer_roles/seller_roles.legacy_entry_id directly,
# same one-hop simplification.
#
# `notes.id` reuses the SOURCE `note` record's own Attio record id verbatim
# (already a UUID) as the Postgres primary key -- upserts are ON CONFLICT(id).

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }

$env:WUSOOL_SOURCE_ATTIO_API_KEY = $SourceApiKey.Trim()
$env:WUSOOL_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_APPLY = if ($Apply) { "1" } else { "0" }

try {
@'
import json, os, sys, time, urllib.error, urllib.request
import psycopg

APPLY = os.environ.get("WUSOOL_APPLY") == "1"
KEY = os.environ["WUSOOL_SOURCE_ATTIO_API_KEY"]
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
            time.sleep(min(60, 5 * (attempt + 1)))

def pages_object(slug):
    result, offset = [], 0
    while True:
        batch = request("POST", f"/objects/{slug}/records/query", {"limit": 500, "offset": offset}).get("data", [])
        result.extend(batch)
        if len(batch) < 500: return result
        offset += 500

def items(v, slug):
    return [x for x in (v.get(slug) or []) if x.get("active_until") is None]

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

print("Reading Postgres organizations/person/buyer_roles/seller_roles...")
with psycopg.connect(os.environ["WUSOOL_DATABASE_URL"], connect_timeout=10) as conn:
    with conn.cursor() as c:
        c.execute("SELECT attio_id FROM organizations")
        org_ids = {r[0] for r in c.fetchall()}
        c.execute("SELECT attio_id FROM person")
        person_ids = {r[0] for r in c.fetchall()}
        c.execute("SELECT id, legacy_entry_id FROM buyer_roles WHERE legacy_entry_id IS NOT NULL")
        buyer_role_by_entry = {entry: str(rid) for rid, entry in c.fetchall()}
        c.execute("SELECT id, legacy_entry_id FROM seller_roles WHERE legacy_entry_id IS NOT NULL")
        seller_role_by_entry = {entry: str(rid) for rid, entry in c.fetchall()}
        c.execute("SELECT id FROM notes")
        existing_note_ids = {str(r[0]) for r in c.fetchall()}

print(f"Organizations: {len(org_ids)}. People: {len(person_ids)}.")
print(f"Buyer Role rows: {len(buyer_role_by_entry)}. Seller Role rows: {len(seller_role_by_entry)}.")
print(f"Existing Postgres notes: {len(existing_note_ids)}.")

print("Fetching SOURCE Attio 'note' object records...")
notes = pages_object("note")
print(f"SOURCE note records: {len(notes)}.")

to_upsert = []
skipped_no_org_and_no_person = 0
for r in notes:
    v = r.get("values") or {}
    note_id = record_id(r)
    org_attio_id = ref(v, "organization_id")
    if org_attio_id and org_attio_id not in org_ids: org_attio_id = None
    person_attio_id = ref(v, "person_id")
    if person_attio_id and person_attio_id not in person_ids: person_attio_id = None
    if not org_attio_id and not person_attio_id:
        skipped_no_org_and_no_person += 1
        continue

    buyer_role_entry = first(v, "buyer_role_id")
    seller_role_entry = first(v, "seller_role_id")
    buyer_role_id = buyer_role_by_entry.get(buyer_role_entry) if buyer_role_entry else None
    seller_role_id = seller_role_by_entry.get(seller_role_entry) if seller_role_entry else None

    to_upsert.append({
        "id": note_id,
        "organization_id": org_attio_id,
        "person_id": person_attio_id,
        "buyer_role_id": buyer_role_id,
        "seller_role_id": seller_role_id,
        "note_type": first(v, "note_type"),
        "content": first(v, "content"),
        # Slug is note_created_at, not created_at -- Attio reserves created_at
        # as a protected system attribute on every custom object.
        "created_at": first(v, "note_created_at"),
    })

new_count = sum(1 for n in to_upsert if n["id"] not in existing_note_ids)
print(f"Notes to upsert: {len(to_upsert)} ({new_count} new, {len(to_upsert) - new_count} already present). Skipped (neither org nor person resolved): {skipped_no_org_and_no_person}.")
for sample in to_upsert[:5]:
    preview = (sample["content"] or "")[:80]
    print(f"  SAMPLE: {sample['id']} [{sample['note_type']}] org={sample['organization_id']} person={sample['person_id']} content=\"{preview}\"")

if not APPLY:
    print("DRY RUN complete. Add -Apply to write these rows.")
    sys.exit(0)

with psycopg.connect(os.environ["WUSOOL_DATABASE_URL"], connect_timeout=10) as conn:
    with conn.cursor() as c:
        c.execute("SELECT current_database()")
        if c.fetchone()[0] != "wusool_crm":
            raise RuntimeError("Refusing to write outside wusool_crm")
        rows = [(
            n["id"], n["organization_id"], n["person_id"], n["buyer_role_id"], n["seller_role_id"],
            n["note_type"], n["content"], n["created_at"],
        ) for n in to_upsert]
        c.executemany(
            """INSERT INTO notes(id, organization_id, person_id, buyer_role_id, seller_role_id, note_type, content, created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,COALESCE(%s, now()))
               ON CONFLICT(id) DO UPDATE SET
                 organization_id=excluded.organization_id, person_id=excluded.person_id,
                 buyer_role_id=excluded.buyer_role_id, seller_role_id=excluded.seller_role_id,
                 note_type=excluded.note_type, content=excluded.content,
                 created_at=COALESCE(excluded.created_at, notes.created_at)""",
            rows,
        )
    conn.commit()
print(f"Upserted {len(to_upsert)} notes into PostgreSQL.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "Notes sync from SOURCE failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_SOURCE_ATTIO_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_APPLY -ErrorAction SilentlyContinue
}
