param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL
)

# Prod's equivalent of ../dev-postgres-sync/validate-postgres.ps1, comparing
# against SOURCE Attio's custom objects instead of DEV Attio. Read-only.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }
py -c "import psycopg" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Install the PostgreSQL driver: py -m pip install 'psycopg[binary]'" }

$env:WUSOOL_VALIDATE_SOURCE_KEY = $SourceApiKey.Trim()
$env:WUSOOL_VALIDATE_DATABASE_URL = $DatabaseUrl

try {
@'
import json, os, sys, time, urllib.error, urllib.request
import psycopg

base="https://api.attio.com/v2"
headers={"Authorization":f"Bearer {os.environ['WUSOOL_VALIDATE_SOURCE_KEY']}","Accept":"application/json","Content-Type":"application/json"}

def request(method,path,body=None):
  payload=None if body is None else json.dumps(body).encode()
  for attempt in range(8):
    try:
      req=urllib.request.Request(base+path,data=payload,headers=headers,method=method)
      with urllib.request.urlopen(req,timeout=90) as response:return json.loads(response.read())
    except urllib.error.HTTPError as exc:
      if (exc.code!=429 and exc.code<500) or attempt==7:raise
      time.sleep(min(90,15*(attempt+1)))

def count_pages(path):
  total=offset=0
  while True:
    page=request("POST",path,{"limit":500,"offset":offset}).get("data",[])
    total+=len(page)
    if len(page)<500:return total
    offset+=500

source={
  "organizations":count_pages("/objects/organizations/records/query"),
  "person":count_pages("/objects/person/records/query"),
  "deals":count_pages("/objects/deal/records/query"),
  "buyer_roles":count_pages("/lists/buyer_role/entries/query"),
  "seller_roles":count_pages("/lists/seller_role/entries/query"),
}

failures=[]
with psycopg.connect(os.environ["WUSOOL_VALIDATE_DATABASE_URL"],connect_timeout=10) as conn:
  with conn.cursor() as cursor:
    cursor.execute("select current_database()")
    database=cursor.fetchone()[0]
    if database!="wusool_crm":raise RuntimeError(f"Refusing validation outside wusool_crm: {database}")
    print("\nSOURCE Attio to prod PostgreSQL count validation")
    print("-"*67)
    print(f"{'Entity':18} {'SOURCE Attio':>12} {'PostgreSQL':>12} {'Status':>12}")
    print("-"*67)
    for table,expected in source.items():
      query="select count(*) from organizations where removed_at is null" if table=="organizations" else ("select count(*) from person where removed_at is null" if table=="person" else f"select count(*) from {table}")
      cursor.execute(query)
      actual=cursor.fetchone()[0]
      status="PASS" if actual==expected else "FAIL"
      print(f"{table:18} {expected:12} {actual:12} {status:>12}")
      if actual!=expected:failures.append(f"{table}: SOURCE={expected}, PostgreSQL={actual}")

    integrity={
      "person missing organization": "select count(*) from person p where p.company_attio_id is not null and not exists(select 1 from organizations o where o.attio_id=p.company_attio_id)",
      "deals missing buyer organization": "select count(*) from deals d where d.buyer_organization_attio_id is not null and not exists(select 1 from organizations o where o.attio_id=d.buyer_organization_attio_id)",
      "deals missing buyer person": "select count(*) from deals d where d.buyer_person_attio_id is not null and not exists(select 1 from person p where p.attio_id=d.buyer_person_attio_id)",
      "deals missing seller": "select count(*) from deals d where d.seller_organization_attio_id is not null and not exists(select 1 from organizations o where o.attio_id=d.seller_organization_attio_id)",
      "buyer roles missing organization": "select count(*) from buyer_roles b where not exists(select 1 from organizations o where o.attio_id=b.org_attio_id)",
      "seller roles missing organization": "select count(*) from seller_roles s where not exists(select 1 from organizations o where o.attio_id=s.org_attio_id)",
      "notes missing org and person": "select count(*) from notes n where n.organization_id is null and n.person_id is null",
      "activities missing organization": "select count(*) from activities a where a.subject_type='Organization' and not exists(select 1 from organizations o where o.attio_id=a.subject_attio_id)",
      "activities missing person": "select count(*) from activities a where a.subject_type='Person' and not exists(select 1 from person p where p.attio_id=a.subject_attio_id)",
      "activities missing seller role": "select count(*) from activities a where a.subject_type='SellerRole' and not exists(select 1 from seller_roles s where s.id=a.subject_uuid)",
    }
    print("\nRelationship integrity")
    print("-"*67)
    for label,query in integrity.items():
      cursor.execute(query);count=cursor.fetchone()[0]
      status="PASS" if count==0 else "FAIL"
      print(f"{label:45} {count:8} {status:>8}")
      if count:failures.append(f"{label}: {count}")

if failures:
  print("\nVALIDATION FAILED")
  for failure in failures:print(f"- {failure}")
  sys.exit(1)
print("\nVALIDATION PASSED: counts and key relationships match SOURCE Attio.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL validation failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_VALIDATE_SOURCE_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_VALIDATE_DATABASE_URL -ErrorAction SilentlyContinue
}
