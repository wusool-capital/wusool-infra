param(
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Reset,
  [string]$ConfirmDatabase
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }
py -c "import psycopg" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Install the PostgreSQL driver: py -m pip install 'psycopg[binary]'" }
if ($Reset -and $ConfirmDatabase -ne "wusool_crm") {
  throw "A reset requires exactly: -Reset -ConfirmDatabase wusool_crm"
}

$env:WUSOOL_SETUP_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_SETUP_RESET = if ($Reset) { "1" } else { "0" }
$schemaPath = (Resolve-Path (Join-Path $PSScriptRoot "sql")).Path

try {
@'
import os, pathlib, psycopg

url=os.environ["WUSOOL_SETUP_DATABASE_URL"]
reset=os.environ.get("WUSOOL_SETUP_RESET")=="1"
schema_path=pathlib.Path(os.sys.argv[1])
required={
 "users","organizations","people","deals","mandates","buyer_roles",
 "seller_roles","scorecards","activities","deal_stage_events","signals",
 "buyer_intel","seller_financials","mandate_targets","match_scores",
 "documents","vertical_kb","graph_edges","attio_sync_state","attio_raw_events"
}

with psycopg.connect(url,autocommit=True,connect_timeout=10) as conn:
  with conn.cursor() as c:
    c.execute("select current_database()")
    database=c.fetchone()[0]
    if database!="wusool_crm": raise RuntimeError(f"Refusing setup outside wusool_crm: {database}")
    print(f"Verified database: {database}")
    if reset:
      c.execute("drop schema public cascade")
      c.execute("create schema public")
      c.execute("grant all on schema public to public")
      print("Old public schema removed and recreated.")
    for file in sorted(schema_path.glob("*.sql")):
      print(f"Running {file.name}")
      c.execute(file.read_text(encoding="utf-8-sig"),prepare=False)
    c.execute("select table_name from information_schema.tables where table_schema='public'")
    found={row[0] for row in c.fetchall()}
    missing=sorted(required-found)
    if missing: raise RuntimeError("Missing tables: "+", ".join(missing))
    required_columns={
      "deals":{"stage_changed_at","time_in_stage","contract_signed_date","exclusivity_date","cim_ready","deal_memo_ready"},
      "seller_roles":{"relationship_status","sell_timeline","intake_source","last_attempt_date","last_attempt_channel","last_attempt_outcome"},
      "buyer_roles":{"acquisition_enrichment","deals_introduced","deals_converted"},
      "organizations":{"funding_raised","estimated_arr","removed_at"}
    }
    for table,expected in required_columns.items():
      c.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s",(table,))
      actual={row[0] for row in c.fetchall()}
      missing=sorted(expected-actual)
      if missing: raise RuntimeError(f"Missing {table} columns: {', '.join(missing)}")
    print(f"Schema validation passed: {len(required)} required tables.")
'@ | py - $schemaPath
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL setup failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_SETUP_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_SETUP_RESET -ErrorAction SilentlyContinue
}
