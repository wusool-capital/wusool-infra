param(
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }
if ($Apply -and [string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }

$env:WUSOOL_DEV_ATTIO_API_KEY = $DevApiKey.Trim()
$env:WUSOOL_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_SYNC_APPLY = if ($Apply) { "1" } else { "0" }

try {
@'
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime

APPLY = os.environ.get("WUSOOL_SYNC_APPLY") == "1"
KEY = os.environ["WUSOOL_DEV_ATTIO_API_KEY"]
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
    for path in (("value",), ("option","title"), ("status","title"), ("email_address",), ("domain",), ("timestamp",), ("date",)):
        cur = x
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is not None: return cur
    return None
def titles(v, slug):
    out=[]
    for x in items(v, slug):
        value=(x.get("option") or {}).get("title") or (x.get("status") or {}).get("title") or x.get("value")
        if value is not None and value not in out: out.append(str(value))
    return out
def ref(v, slug):
    xs=items(v,slug)
    return (xs[0].get("target_record_id") if xs else None)
def refs(v, slug): return [x.get("target_record_id") for x in items(v,slug) if x.get("target_record_id")]
def actor(v, slug):
    xs=items(v,slug)
    if not xs:return None
    return xs[0].get("referenced_actor_id") or xs[0].get("workspace_member_id")
def boolean(v, slug):
    value=first(v,slug)
    if value is None:return None
    if isinstance(value,bool):return value
    return str(value).lower() in ("true","yes","1","checked")
def number(v, slug):
    value=first(v,slug)
    if value in (None,""):return None
    try:return float(value)
    except:return None
def integer(v, slug):
    value=number(v,slug)
    return None if value is None else int(value)
def money(v, slug):
    xs=items(v,slug)
    if not xs:return None
    x=xs[0]; amount=x.get("currency_value",x.get("value")); currency=x.get("currency_code",x.get("currency"))
    if amount in (None,""):return None
    return {"amount":amount,"currency":currency}
def record_id(r): return str((r.get("id") or {}).get("record_id") or r.get("record_id") or "")
def entry_id(r): return str((r.get("id") or {}).get("entry_id") or r.get("entry_id") or "")
def parent_id(r):
    value=r.get("parent_record_id")
    return str((value or {}).get("record_id") if isinstance(value,dict) else value or (r.get("id") or {}).get("record_id") or "")
def raw(value): return json.dumps(value,ensure_ascii=False)
def domains(v):
    value=first(v,"domains")
    if isinstance(value,list):return value
    return [x.strip() for x in str(value or "").split(",") if x.strip()]

print("Reading canonical DEV Attio...")
organizations=pages("/objects/organizations/records/query")
people=pages("/objects/person/records/query")
deals=pages("/objects/deals/records/query")
buyer_entries=pages("/lists/buyer_role/entries/query")
seller_entries=pages("/lists/seller_role/entries/query")
mandate_entries=pages("/lists/mandates/entries/query")
try: members=request("GET","/workspace_members").get("data",[])
except Exception as exc:
    print(f"WARNING: workspace members unavailable: {exc}"); members=[]

counts={"users":len(members),"organizations":len(organizations),"people":len(people),"deals":len(deals),"buyer_roles":len(buyer_entries),"seller_roles":len(seller_entries),"mandates":len(mandate_entries)}
for name,count in counts.items(): print(f"{name:16} {count}")
if not APPLY:
    print("DRY RUN complete. Add -Apply to upsert into PostgreSQL.")
    sys.exit(0)

import psycopg
from psycopg.types.json import Jsonb
def J(value): return None if value is None else Jsonb(value)

with psycopg.connect(os.environ["WUSOOL_DATABASE_URL"], connect_timeout=10) as conn:
  with conn.cursor() as c:
    c.execute("SELECT current_database()")
    if c.fetchone()[0] != "wusool_crm": raise RuntimeError("Refusing sync outside wusool_crm")

    user_rows=[]
    for m in members:
      mid=str((m.get("id") or {}).get("workspace_member_id") or m.get("workspace_member_id") or m.get("id") or "")
      if not mid:continue
      name=m.get("name") or " ".join(x for x in (m.get("first_name"),m.get("last_name")) if x) or m.get("email_address") or mid
      user_rows.append((mid,name,m.get("email_address"),m.get("access_level"),not bool(m.get("is_suspended")),J(m)))
    c.executemany("""INSERT INTO users(attio_id,name,email,access,active,raw_attio) VALUES(%s,%s,%s,%s,%s,%s)
      ON CONFLICT(attio_id) DO UPDATE SET name=excluded.name,email=excluded.email,access=excluded.access,active=excluded.active,raw_attio=excluded.raw_attio,updated_at=now()""",user_rows)
    user_ids={r[0] for r in user_rows}

    org_rows=[]
    for r in organizations:
      v=vals(r); rid=record_id(r)
      org_rows.append((rid,first(v,"name") or f"Unnamed DEV Organization [{rid}]",first(v,"description"),titles(v,"type"),first(v,"client_type"),titles(v,"sector_focus"),titles(v,"stage"),titles(v,"geographic_focus"),first(v,"hq_country"),domains(v),titles(v,"categories"),first(v,"relationship_status"),first(v,"strongest_connection_strength"),actor(v,"owner") if actor(v,"owner") in user_ids else None,first(v,"last_interaction_at"),J(money(v,"funding_raised")),first(v,"estimated_arr"),J(r)))
    c.executemany("""INSERT INTO organizations(attio_id,name,description,type,client_type,sector_focus,stage_focus,geographic_focus,hq_country,domains,categories,relationship_status,connection_strength,owner_attio_id,last_interaction_at,funding_raised,estimated_arr,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(attio_id) DO UPDATE SET name=excluded.name,description=excluded.description,type=excluded.type,client_type=excluded.client_type,sector_focus=excluded.sector_focus,stage_focus=excluded.stage_focus,geographic_focus=excluded.geographic_focus,hq_country=excluded.hq_country,domains=excluded.domains,categories=excluded.categories,relationship_status=excluded.relationship_status,connection_strength=excluded.connection_strength,owner_attio_id=excluded.owner_attio_id,last_interaction_at=excluded.last_interaction_at,funding_raised=excluded.funding_raised,estimated_arr=excluded.estimated_arr,raw_attio=excluded.raw_attio,updated_at=now()""",org_rows)
    org_ids={r[0] for r in org_rows}

    person_rows=[]
    for r in people:
      v=vals(r); rid=record_id(r); company=ref(v,"company")
      emails=[x.get("email_address") for x in items(v,"email_addresses") if x.get("email_address")]
      roles=titles(v,"role") or titles(v,"job_title")
      person_rows.append((rid,first(v,"name") or f"Unnamed DEV Person [{rid}]",", ".join(roles) or first(v,"role"),company if company in org_ids else None,emails,first(v,"linkedin"),first(v,"relationship_status"),first(v,"strongest_connection_strength"),actor(v,"owner") if actor(v,"owner") in user_ids else None,first(v,"last_interaction_at"),J(r)))
    c.executemany("""INSERT INTO people(attio_id,name,role,company_attio_id,email,linkedin,relationship_status,connection_strength,owner_attio_id,last_interaction_at,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(attio_id) DO UPDATE SET name=excluded.name,role=excluded.role,company_attio_id=excluded.company_attio_id,email=excluded.email,linkedin=excluded.linkedin,relationship_status=excluded.relationship_status,connection_strength=excluded.connection_strength,owner_attio_id=excluded.owner_attio_id,last_interaction_at=excluded.last_interaction_at,raw_attio=excluded.raw_attio,updated_at=now()""",person_rows)
    person_ids={r[0] for r in person_rows}

    deal_rows=[]
    for r in deals:
      v=vals(r); rid=record_id(r); buyer=ref(v,"buyer_id"); seller=ref(v,"seller_id")
      deal_rows.append((rid,first(v,"name") or f"Unnamed DEV Deal [{rid}]",first(v,"stage"),first(v,"stage_changed_at"),buyer if buyer in org_ids else None,buyer if buyer in person_ids else None,seller if seller in org_ids else None,actor(v,"owner") if actor(v,"owner") in user_ids else None,J(money(v,"value") or money(v,"deal_value")),first(v,"teaser_status"),int(number(v,"nda_count") or 0),boolean(v,"cim_ready"),boolean(v,"deal_memo_ready"),first(v,"contract_signed_date"),first(v,"exclusivity_date"),ref(v,"next_due_task") or first(v,"next_task"),first(v,"data_room_substatus"),J(r)))
    c.executemany("""INSERT INTO deals(attio_id,name,stage,stage_changed_at,buyer_organization_attio_id,buyer_person_attio_id,seller_organization_attio_id,owner_attio_id,value,teaser_status,nda_count,cim_ready,deal_memo_ready,contract_signed_date,exclusivity_date,next_task,data_room_substatus,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(attio_id) DO UPDATE SET name=excluded.name,stage=excluded.stage,stage_changed_at=excluded.stage_changed_at,buyer_organization_attio_id=excluded.buyer_organization_attio_id,buyer_person_attio_id=excluded.buyer_person_attio_id,seller_organization_attio_id=excluded.seller_organization_attio_id,owner_attio_id=excluded.owner_attio_id,value=excluded.value,teaser_status=excluded.teaser_status,nda_count=excluded.nda_count,cim_ready=excluded.cim_ready,deal_memo_ready=excluded.deal_memo_ready,contract_signed_date=excluded.contract_signed_date,exclusivity_date=excluded.exclusivity_date,next_task=excluded.next_task,data_room_substatus=excluded.data_room_substatus,raw_attio=excluded.raw_attio,updated_at=now()""",deal_rows)

    mandate_rows=[]
    for e in mandate_entries:
      v=vals(e); eid=entry_id(e); buyer=ref(v,"buyer_id") or parent_id(e); seller=ref(v,"seller_id")
      mandate_rows.append((eid,first(v,"side") or "buy",buyer if buyer in org_ids else None,seller if seller in org_ids else None,first(v,"phase"),[x for x in refs(v,"assigned_advisor") if x in user_ids],first(v,"start_date"),first(v,"expiry_date"),boolean(v,"universe_constructed"),boolean(v,"shortlist_approved"),integer(v,"universe_size"),integer(v,"shortlist_size"),integer(v,"tier1_contacted"),integer(v,"responses"),J(e)))
    c.executemany("""INSERT INTO mandates(attio_id,side,buyer_attio_id,seller_attio_id,phase,assigned_advisor_attio_ids,start_date,expiry_date,universe_constructed,shortlist_approved,universe_size,shortlist_size,tier1_contacted,responses,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,false),COALESCE(%s,false),%s,%s,%s,%s,%s)
      ON CONFLICT(attio_id) DO UPDATE SET side=excluded.side,buyer_attio_id=excluded.buyer_attio_id,seller_attio_id=excluded.seller_attio_id,phase=excluded.phase,assigned_advisor_attio_ids=excluded.assigned_advisor_attio_ids,start_date=excluded.start_date,expiry_date=excluded.expiry_date,universe_constructed=excluded.universe_constructed,shortlist_approved=excluded.shortlist_approved,universe_size=excluded.universe_size,shortlist_size=excluded.shortlist_size,tier1_contacted=excluded.tier1_contacted,responses=excluded.responses,raw_attio=excluded.raw_attio,updated_at=now()""",mandate_rows)

    buyer_rows=[]
    for e in buyer_entries:
      v=vals(e); org=parent_id(e); contact=ref(v,"key_contact")
      buyer_rows.append((org,first(v,"model"),first(v,"mandate_status"),J(money(v,"ebitda_floor")),J(money(v,"check_size_min")),J(money(v,"check_size_max")),J(money(v,"ev_ceiling")),first(v,"deal_structure_tolerance"),boolean(v,"earnout_tolerance"),boolean(v,"profitable_only"),first(v,"investment_strategy"),first(v,"notes"),contact if contact in person_ids else None,first(v,"acquisition_enrichment"),integer(v,"deals_introduced"),integer(v,"deals_converted"),J(e)))
    c.executemany("""INSERT INTO buyer_roles(org_attio_id,model,mandate_status,ebitda_floor,check_size_min,check_size_max,ev_ceiling,deal_structure_tolerance,earnout_tolerance,profitable_only,investment_strategy,notes,key_contact_attio_id,acquisition_enrichment,deals_introduced,deals_converted,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(org_attio_id) DO UPDATE SET model=excluded.model,mandate_status=excluded.mandate_status,ebitda_floor=excluded.ebitda_floor,check_size_min=excluded.check_size_min,check_size_max=excluded.check_size_max,ev_ceiling=excluded.ev_ceiling,deal_structure_tolerance=excluded.deal_structure_tolerance,earnout_tolerance=excluded.earnout_tolerance,profitable_only=excluded.profitable_only,investment_strategy=excluded.investment_strategy,notes=excluded.notes,key_contact_attio_id=excluded.key_contact_attio_id,acquisition_enrichment=excluded.acquisition_enrichment,deals_introduced=excluded.deals_introduced,deals_converted=excluded.deals_converted,raw_attio=excluded.raw_attio,updated_at=now()""",buyer_rows)

    c.execute("SELECT attio_id,id FROM mandates WHERE attio_id IS NOT NULL")
    mandate_uuid=dict(c.fetchall())
    seller_rows=[]
    for e in seller_entries:
      v=vals(e); org=parent_id(e); mandate=ref(v,"mandate_id")
      seller_rows.append((org,first(v,"outreach_tier"),first(v,"appetite_signal"),first(v,"relationship_status"),J(money(v,"est_revenue")),J(money(v,"est_ebitda")),J(money(v,"owner_salary")),J(money(v,"valuation_low")),J(money(v,"valuation_mid")),J(money(v,"valuation_high")),first(v,"sell_timeline"),number(v,"readiness_score"),first(v,"readiness_band"),first(v,"intake_source"),mandate_uuid.get(mandate),first(v,"last_attempt_date"),first(v,"last_attempt_channel"),first(v,"last_attempt_outcome"),number(v,"lead_quality_score"),first(v,"re_engage_date"),J(e)))
    c.executemany("""INSERT INTO seller_roles(org_attio_id,outreach_tier,appetite_signal,relationship_status,est_revenue,est_ebitda,owner_salary,valuation_low,valuation_mid,valuation_high,sell_timeline,readiness_score,readiness_band,intake_source,mandate_id,last_attempt_date,last_attempt_channel,last_attempt_outcome,lead_quality_score,re_engage_date,raw_attio)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(org_attio_id) DO UPDATE SET outreach_tier=excluded.outreach_tier,appetite_signal=excluded.appetite_signal,relationship_status=excluded.relationship_status,est_revenue=excluded.est_revenue,est_ebitda=excluded.est_ebitda,owner_salary=excluded.owner_salary,valuation_low=excluded.valuation_low,valuation_mid=excluded.valuation_mid,valuation_high=excluded.valuation_high,sell_timeline=excluded.sell_timeline,readiness_score=excluded.readiness_score,readiness_band=excluded.readiness_band,intake_source=excluded.intake_source,mandate_id=excluded.mandate_id,last_attempt_date=excluded.last_attempt_date,last_attempt_channel=excluded.last_attempt_channel,last_attempt_outcome=excluded.last_attempt_outcome,lead_quality_score=excluded.lead_quality_score,re_engage_date=excluded.re_engage_date,raw_attio=excluded.raw_attio,updated_at=now()""",seller_rows)
  with conn.cursor() as check:
    for table, expected in counts.items():
      check.execute(f"SELECT count(*) FROM {table}")
      actual=check.fetchone()[0]
      print(f"validated {table:16} expected={expected} actual={actual}")
      if actual != expected:
        raise RuntimeError(f"Count mismatch for {table}: expected {expected}, found {actual}")
  conn.commit()
print("PostgreSQL sync committed successfully.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "DEV Attio to PostgreSQL sync failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_DEV_ATTIO_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_SYNC_APPLY -ErrorAction SilentlyContinue
}
