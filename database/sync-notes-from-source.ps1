param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply
)

# Populates PostgreSQL's `notes` table directly from SOURCE Attio's own
# `note` custom object (workflows/crm-sync/scripts/source-attio/backfill-notes.ps1)
# -- NOT through DEV Attio, which has no notes object yet. Every other table
# in this database/ folder is synced DEV Attio -> Postgres (see
# sync-postgres.ps1); this one is the deliberate exception, same reasoning as
# the (now-removed) meeting-notes bridge script from earlier this session.
#
# organization_id/person_id link to Postgres's EXISTING organizations/person
# rows (which are keyed by DEV Attio's attio_id) by bridging through SOURCE
# record ids: organizations.raw_attio / person.raw_attio already hold the
# full DEV record JSON (from sync-postgres.ps1), including DEV's own
# legacy_attio_id value -- the original SOURCE record id DEV was migrated
# from. That SOURCE id is exactly what this SOURCE `note` object's
# organization_id/person_id record-references point at, so matching on it
# bridges SOURCE -> Postgres without any DEV Attio API call at all.
#
# buyer_role_id/seller_role_id need no separate id-matching scheme: both
# buyer_roles/seller_roles are one-row-per-org (UNIQUE org_attio_id), so once
# a note's organization is resolved, its buyer/seller role row (if any) is
# just a lookup by that org's attio_id -- not by matching the SOURCE list
# entry id the `note` object happens to store.
#
# `notes.id` reuses the SOURCE `note` record's own Attio record id verbatim
# (already a UUID) as the Postgres primary key -- no separate idempotency
# column needed, upserts are ON CONFLICT(id) DO UPDATE.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
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
from psycopg.types.json import Jsonb

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
        c.execute("SELECT attio_id, raw_attio FROM organizations")
        org_rows = c.fetchall()
        c.execute("SELECT attio_id, raw_attio FROM person")
        person_rows = c.fetchall()
        c.execute("SELECT id, org_attio_id FROM buyer_roles")
        buyer_role_rows = c.fetchall()
        c.execute("SELECT id, org_attio_id FROM seller_roles")
        seller_role_rows = c.fetchall()
        c.execute("SELECT id FROM notes")
        existing_note_ids = {str(r[0]) for r in c.fetchall()}

def legacy_id(raw_attio):
    return first((raw_attio or {}).get("values") or {}, "legacy_attio_id")

org_by_source_id = {}
for attio_id, raw_attio in org_rows:
    legacy = legacy_id(raw_attio)
    if legacy: org_by_source_id[str(legacy)] = attio_id
person_by_source_id = {}
for attio_id, raw_attio in person_rows:
    legacy = legacy_id(raw_attio)
    if legacy: person_by_source_id[str(legacy)] = attio_id
buyer_role_by_org = {org_attio_id: str(role_id) for role_id, org_attio_id in buyer_role_rows}
seller_role_by_org = {org_attio_id: str(role_id) for role_id, org_attio_id in seller_role_rows}

print(f"Organizations: {len(org_rows)} ({len(org_by_source_id)} bridgeable via legacy_attio_id).")
print(f"People: {len(person_rows)} ({len(person_by_source_id)} bridgeable via legacy_attio_id).")
print(f"Buyer Role rows: {len(buyer_role_by_org)}. Seller Role rows: {len(seller_role_by_org)}.")
print(f"Existing Postgres notes: {len(existing_note_ids)}.")

print("Fetching SOURCE Attio 'note' object records...")
notes = pages_object("note")
print(f"SOURCE note records: {len(notes)}.")

to_upsert = []
skipped_no_org = 0
for r in notes:
    v = r.get("values") or {}
    note_id = record_id(r)
    source_org_id = ref(v, "organization_id")
    org_attio_id = org_by_source_id.get(source_org_id) if source_org_id else None
    if not org_attio_id:
        skipped_no_org += 1
        continue

    source_person_id = ref(v, "person_id")
    person_attio_id = person_by_source_id.get(source_person_id) if source_person_id else None

    buyer_role_text = first(v, "buyer_role_id")
    seller_role_text = first(v, "seller_role_id")
    buyer_role_id = buyer_role_by_org.get(org_attio_id) if buyer_role_text else None
    seller_role_id = seller_role_by_org.get(org_attio_id) if seller_role_text else None

    to_upsert.append({
        "id": note_id,
        "organization_id": org_attio_id,
        "person_id": person_attio_id,
        "buyer_role_id": buyer_role_id,
        "seller_role_id": seller_role_id,
        "note_type": first(v, "note_type"),
        "content": first(v, "content"),
        # Slug is note_created_at, not created_at -- Attio reserves created_at
        # as a protected system attribute on every custom object; see
        # backfill-notes.ps1's field list comment.
        "created_at": first(v, "note_created_at"),
    })

new_count = sum(1 for n in to_upsert if n["id"] not in existing_note_ids)
print(f"Notes to upsert: {len(to_upsert)} ({new_count} new, {len(to_upsert) - new_count} already present). Skipped (org not resolved): {skipped_no_org}.")
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
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(id) DO UPDATE SET
                 organization_id=excluded.organization_id, person_id=excluded.person_id,
                 buyer_role_id=excluded.buyer_role_id, seller_role_id=excluded.seller_role_id,
                 note_type=excluded.note_type, content=excluded.content, created_at=excluded.created_at""",
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
