param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$env:WUSOOL_VALIDATE_SOURCE_KEY = $SourceApiKey.Trim()
$env:WUSOOL_VALIDATE_DEV_KEY = $DevApiKey.Trim()
$env:WUSOOL_VALIDATE_DEV_WORKSPACE = [string]$decisions.dev_workspace_id
$env:WUSOOL_VALIDATE_MAPPING = Join-Path $PSScriptRoot "config\source-to-target-mapping.json"

try {
@'
import json, os, sys, time, urllib.error, urllib.request

BASE = "https://api.attio.com/v2"

def request(key, method, path, body=None):
  headers = {
    "Authorization": f"Bearer {key}",
    "Accept": "application/json",
    "Content-Type": "application/json",
  }
  payload = None if body is None else json.dumps(body).encode()
  for attempt in range(8):
    try:
      req = urllib.request.Request(BASE + path, data=payload, headers=headers, method=method)
      with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read())
    except urllib.error.HTTPError as exc:
      if (exc.code != 429 and exc.code < 500) or attempt == 7:
        raise
      time.sleep(min(90, 15 * (attempt + 1)))

def pages(key, path):
  rows, offset = [], 0
  while True:
    page = request(key, "POST", path, {"limit": 500, "offset": offset}).get("data", [])
    rows.extend(page)
    if len(page) < 500:
      return rows
    offset += 500

def record_id(row):
  return row.get("id", {}).get("record_id")

def parent_id(entry):
  parent = entry.get("parent_record_id") or entry.get("parent_record") or {}
  if isinstance(parent, str):
    return parent
  if isinstance(parent, dict):
    return parent.get("record_id") or parent.get("id", {}).get("record_id")
  return None

source_key = os.environ["WUSOOL_VALIDATE_SOURCE_KEY"]
dev_key = os.environ["WUSOOL_VALIDATE_DEV_KEY"]
expected_workspace = os.environ["WUSOOL_VALIDATE_DEV_WORKSPACE"]
with open(os.environ["WUSOOL_VALIDATE_MAPPING"], encoding="utf-8-sig") as stream:
  mapping = json.load(stream)

workspace = request(dev_key, "GET", "/objects/organizations").get("data", {}).get("id", {}).get("workspace_id")
if workspace != expected_workspace:
  raise RuntimeError(f"DEV workspace mismatch. Expected {expected_workspace}, connected to {workspace}")

object_routes = []
for source_name, definition in mapping["objects"].items():
  object_routes.append((source_name, definition["target"]))

list_routes = []
for target_name in ("buyer_role", "seller_role", "mandates"):
  definition = mapping["lists"][target_name]
  list_routes.append((definition["source"], definition["target"]))

failures = []
print("\nSOURCE to DEV Attio object count validation")
print("-" * 78)
print(f"{'Route':32} {'SOURCE':>10} {'DEV':>10} {'Status':>10}")
print("-" * 78)
for source_object, dev_object in object_routes:
  source_rows = pages(source_key, f"/objects/{source_object}/records/query")
  dev_rows = pages(dev_key, f"/objects/{dev_object}/records/query")
  source_count, dev_count = len(source_rows), len(dev_rows)
  status = "PASS" if source_count == dev_count else "FAIL"
  route = f"{source_object} -> {dev_object}"
  print(f"{route:32} {source_count:10} {dev_count:10} {status:>10}")
  if source_count != dev_count:
    failures.append(f"{route}: SOURCE={source_count}, DEV={dev_count}")

print("\nSOURCE to DEV Attio list count validation")
print("-" * 92)
print(f"{'Route':34} {'SOURCE raw':>12} {'canonical':>12} {'DEV':>10} {'Status':>10}")
print("-" * 92)
for source_list, dev_list in list_routes:
  source_rows = pages(source_key, f"/lists/{source_list}/entries/query")
  dev_rows = pages(dev_key, f"/lists/{dev_list}/entries/query")
  source_parents = [parent_id(row) for row in source_rows]
  canonical_count = len({value for value in source_parents if value})
  missing_source_parents = sum(value is None for value in source_parents)
  dev_parents = [parent_id(row) for row in dev_rows]
  duplicate_dev_parents = len([value for value in dev_parents if value]) - len({value for value in dev_parents if value})
  dev_count = len(dev_rows)
  status = "PASS" if canonical_count == dev_count and missing_source_parents == 0 and duplicate_dev_parents == 0 else "FAIL"
  route = f"{source_list} -> {dev_list}"
  print(f"{route:34} {len(source_rows):12} {canonical_count:12} {dev_count:10} {status:>10}")
  if canonical_count != dev_count:
    failures.append(f"{route}: canonical SOURCE={canonical_count}, DEV={dev_count}")
  if missing_source_parents:
    failures.append(f"{source_list}: {missing_source_parents} SOURCE entries have no parent")
  if duplicate_dev_parents:
    failures.append(f"{dev_list}: {duplicate_dev_parents} duplicate DEV parent entries")

if failures:
  print("\nVALIDATION FAILED")
  for failure in failures:
    print(f"- {failure}")
  sys.exit(1)
print("\nVALIDATION PASSED: DEV counts match canonical SOURCE counts.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "Attio validation failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_VALIDATE_SOURCE_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_VALIDATE_DEV_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_VALIDATE_DEV_WORKSPACE -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_VALIDATE_MAPPING -ErrorAction SilentlyContinue
}
