param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply
)

# Prod's equivalent of ../dev-postgres-sync/backfill-activities.ps1. One-time
# historical backfill of the `activities` table's boundary-interaction
# timestamps, which only exist on SOURCE's NATIVE companies/people/
# valuation_tool_leads (SOURCE's custom organizations/person/seller_role
# already collapsed them down during their own native->custom migration).
#
# Crosswalk is one hop here, not two: the dev-postgres-sync version bridges
# native SOURCE id -> DEV Attio id (via DEV org/person's own legacy_attio_id,
# since Postgres there is keyed by DEV's ids). Prod Postgres is keyed
# directly by SOURCE's custom organizations/person/seller_role record ids,
# so this bridges native SOURCE id -> SOURCE custom object id directly (via
# the custom object's own legacy_attio_id) -- one hop, same idea as
# backfill-notes.ps1's own $orgByLegacyId.
#
# The old dev-postgres-sync script also backfills a "Mandate" subject_type
# from the native buy_side_mandates list -- that's the retired DEV Mandates
# list (fully merged into Deal, 2026-08-23); prod has no Mandate-equivalent
# table, so that portion is deliberately omitted here, not adapted.
#
# Idempotent: deletes any existing rows for the same (subject, source
# citation) before inserting, so re-running is always safe.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ($Apply -and [string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }

$env:WUSOOL_SOURCE_ATTIO_API_KEY = $SourceApiKey.Trim()
$env:WUSOOL_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_BACKFILL_APPLY = if ($Apply) { "1" } else { "0" }

try {
@'
import json, os, sys, urllib.error, urllib.request

APPLY = os.environ.get("WUSOOL_BACKFILL_APPLY") == "1"
KEY = os.environ["WUSOOL_SOURCE_ATTIO_API_KEY"]
BASE = "https://api.attio.com/v2"

def request(method, path, body=None):
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "Content-Type": "application/json"}
    req = urllib.request.Request(BASE + path, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read())

def pages(path):
    result, offset = [], 0
    while True:
        batch = request("POST", path, {"limit": 500, "offset": offset}).get("data", [])
        result.extend(batch)
        if len(batch) < 500: return result
        offset += 500

def vals(record): return record.get("values") or record.get("entry_values") or {}
def items(v, slug): return [x for x in (v.get(slug) or []) if x.get("active_until") is None]
def first(v, slug):
    xs = items(v, slug)
    if not xs: return None
    x = xs[0]
    for path in (("value",), ("option","title"), ("status","title"), ("timestamp",), ("date",), ("interacted_at",)):
        cur = x
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is not None: return cur
    return None
def record_id(r): return str((r.get("id") or {}).get("record_id") or r.get("record_id") or "")
def parent_id(r):
    value = r.get("parent_record_id")
    if isinstance(value, dict): return str(value.get("record_id") or "")
    return str(value or (r.get("id") or {}).get("record_id") or "")

print("Reading SOURCE native companies/people/valuation_tool_leads...")
native_companies = pages("/objects/companies/records/query")
native_people = pages("/objects/people/records/query")
native_sellers = pages("/lists/valuation_tool_leads/entries/query")

print("Reading SOURCE custom organizations/person (to bridge native id -> custom record id via legacy_attio_id)...")
custom_orgs = pages("/objects/organizations/records/query")
custom_people = pages("/objects/person/records/query")

org_by_legacy, person_by_legacy = {}, {}
for r in custom_orgs:
    legacy = first(vals(r), "legacy_attio_id")
    if legacy: org_by_legacy[str(legacy)] = record_id(r)
for r in custom_people:
    legacy = first(vals(r), "legacy_attio_id")
    if legacy: person_by_legacy[str(legacy)] = record_id(r)

# subject_type, subject_attio_id, subject_uuid, occurred_at, channel, direction, outcome, source
rows = []

def add_boundary_rows(native_records, subject_type, crosswalk):
    field_channel = [
        ("first_calendar_interaction", "Calendar"), ("last_calendar_interaction", "Calendar"),
        ("next_calendar_interaction", "Calendar"),
        ("first_email_interaction", "Email"), ("last_email_interaction", "Email"),
        ("first_interaction", "Other"), ("next_interaction", "Other"),
    ]
    for r in native_records:
        v = vals(r)
        native_id = record_id(r)
        custom_id = crosswalk.get(native_id)
        if not custom_id: continue
        for field, channel in field_channel:
            ts = first(v, field)
            if not ts: continue
            rows.append((subject_type, custom_id, None, ts, channel, None, None, f"SOURCE {field} backfill"))

add_boundary_rows(native_companies, "Organization", org_by_legacy)
add_boundary_rows(native_people, "Person", person_by_legacy)

attempts = [
    ("attempt_1_date", "attempt_1_channel", "attempt_1_outcome", "attempt_1"),
    ("attempt_2_date", "attempt_2_channel", "attempt_2_outcome", "attempt_2"),
    ("attempt_2_date_3", "attempt_2_channel_6", "attempt_2_outcome_6", "attempt_3"),
]
seller_org_ids = set()
seller_rows_pending = []
for e in native_sellers:
    v = vals(e)
    native_id = parent_id(e)
    org_attio_id = org_by_legacy.get(native_id)
    if not org_attio_id: continue
    for date_f, channel_f, outcome_f, label in attempts:
        ts = first(v, date_f)
        if not ts: continue
        channel = first(v, channel_f) or "Other"
        outcome = first(v, outcome_f)
        seller_org_ids.add(org_attio_id)
        seller_rows_pending.append((org_attio_id, ts, channel, outcome, label))

counts = {
    "Organization": sum(1 for r in rows if r[0] == "Organization"),
    "Person": sum(1 for r in rows if r[0] == "Person"),
    "SellerRole": len(seller_rows_pending),
}
for name, n in counts.items(): print(f"{name:12} {n} rows to backfill")
if not APPLY:
    print("DRY RUN complete. Add -Apply to write into PostgreSQL.")
    sys.exit(0)

import psycopg
with psycopg.connect(os.environ["WUSOOL_DATABASE_URL"], connect_timeout=10) as conn:
  with conn.cursor() as c:
    c.execute("SELECT current_database()")
    if c.fetchone()[0] != "wusool_crm": raise RuntimeError("Refusing backfill outside wusool_crm")

    seller_role_id_by_org = {}
    if seller_org_ids:
        c.execute("SELECT org_attio_id, id FROM seller_roles WHERE org_attio_id = ANY(%s)", (list(seller_org_ids),))
        seller_role_id_by_org = {org: str(sid) for org, sid in c.fetchall()}
    skipped_no_seller_role = 0
    for org_attio_id, ts, channel, outcome, label in seller_rows_pending:
        seller_role_id = seller_role_id_by_org.get(org_attio_id)
        if not seller_role_id:
            skipped_no_seller_role += 1
            continue
        rows.append(("SellerRole", None, seller_role_id, ts, channel, "Out", outcome, f"SOURCE {label} backfill"))
    if skipped_no_seller_role:
        print(f"WARNING: {skipped_no_seller_role} seller attempt row(s) skipped -- no seller_roles Postgres row yet for that organization.")

    # Batched instead of per-row: over an SSM tunnel, ~14k rows x 2 round
    # trips each is the difference between seconds and the better part of an
    # hour. Grouped by (subject_type, source) since within any one group the
    # rows consistently use only subject_attio_id or only subject_uuid, never
    # both -- so one DELETE...ANY(...) per group covers it, then a single
    # executemany for every row's INSERT.
    from collections import defaultdict
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r[0], r[7])].append(r)
    for (subject_type, source), grp in by_key.items():
        attio_ids = [r[1] for r in grp if r[1] is not None]
        uuids = [r[2] for r in grp if r[2] is not None]
        if attio_ids:
            c.execute(
                "DELETE FROM activities WHERE subject_type=%s AND source=%s AND subject_attio_id = ANY(%s)",
                (subject_type, source, attio_ids),
            )
        if uuids:
            c.execute(
                "DELETE FROM activities WHERE subject_type=%s AND source=%s AND subject_uuid = ANY(%s::uuid[])",
                (subject_type, source, uuids),
            )
    c.executemany(
        """INSERT INTO activities(subject_type, subject_attio_id, subject_uuid, ts, channel, direction, outcome, source)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        rows,
    )
    inserted = len(rows)
    conn.commit()
    print(f"Backfilled {inserted} activity rows.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "Activities backfill failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_SOURCE_ATTIO_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_BACKFILL_APPLY -ErrorAction SilentlyContinue
}
