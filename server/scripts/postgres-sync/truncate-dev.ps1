param(
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply,
  [string]$Confirmation
)

# Empty the dev database's Attio-mirrored tables at the single-workspace
# cutover.
#
# Every attio_id in the dev database is a DEV-workspace record id (see
# prod/sync-source-to-prod.ps1's header: SOURCE ids differ from DEV's). The
# dev bot now talks to SOURCE, where those ids do not exist -- so those rows
# are not merely stale, they are broken pointers. An /edit-seller against one
# fails on the scope guard's read-before-write, which reads as a bug in the
# bot rather than as expected. The dev database is a sandbox now, filled by
# /add-* rather than synced from Attio, so it starts empty.
#
# THE SAFETY PROBLEM THIS SCRIPT HAS TO SOLVE
#
# Through an SSM port-forward, dev and prod are indistinguishable from the
# client: both are localhost:15432/wusool_crm. And at cutover the dev
# database still holds ~3,000 organizations mirrored from DEV Attio, so a
# row-count threshold cannot tell them apart either. A fixed -Confirmation
# string would therefore not protect anyone -- it would be just as easy to
# type with the prod tunnel open.
#
# So the confirmation token is derived from the server actually connected to
# (inet_server_addr() -- the RDS instance's own private address, which differs
# between the two VPCs, not the localhost the client sees). The dry run reads
# it and prints the exact token needed; -Apply recomputes it and refuses if it
# does not match. You cannot apply against a database you have not just
# surveyed through this same tunnel.
#
# What that does and does not buy: it stops the realistic accident -- the
# wrong tunnel open, or a token copied from an earlier dev run. It cannot stop
# someone deliberately taking a prod dry run's token and applying it, and it
# would not help in the remote case of both instances sharing an address. The
# row counts printed before the prompt are the backstop for those: a table
# listing 3,000+ organizations alongside populated deals and notes is prod.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found." }
py -c "import psycopg" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Install the PostgreSQL driver: py -m pip install 'psycopg[binary]'" }

$env:WUSOOL_TRUNCATE_DATABASE_URL = $DatabaseUrl
$env:WUSOOL_TRUNCATE_APPLY = if ($Apply) { "1" } else { "0" }
$env:WUSOOL_TRUNCATE_CONFIRMATION = $Confirmation

try {
@'
import os, re, sys
import psycopg

APPLY = os.environ.get("WUSOOL_TRUNCATE_APPLY") == "1"
GIVEN = (os.environ.get("WUSOOL_TRUNCATE_CONFIRMATION") or "").strip()

# The roots. TRUNCATE ... CASCADE walks the foreign-key graph from these, so
# every dependent table is emptied without this script having to enumerate
# (and mis-enumerate) them. The closure is computed and printed first, so
# nothing is emptied that the operator did not see listed.
ROOTS = ["organizations", "person", "deals", "users"]

# Recursively collect every table that references a root, directly or through
# another referencing table -- exactly what CASCADE will reach.
CLOSURE_SQL = """
WITH RECURSIVE refs AS (
  SELECT c.oid::regclass::text AS table_name
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relname = ANY(%s) AND n.nspname = 'public'
  UNION
  SELECT con.conrelid::regclass::text
    FROM pg_constraint con
    JOIN refs r ON con.confrelid::regclass::text = r.table_name
   WHERE con.contype = 'f'
)
SELECT table_name FROM refs ORDER BY table_name
"""

with psycopg.connect(os.environ["WUSOOL_TRUNCATE_DATABASE_URL"]) as conn:
    with conn.cursor() as c:
        c.execute("SELECT current_database(), coalesce(host(inet_server_addr()), 'local'), inet_server_port()")
        database, server, port = c.fetchone()

        c.execute(CLOSURE_SQL, (ROOTS,))
        tables = [row[0] for row in c.fetchall()]

        if "alembic_version" in tables:
            sys.exit("REFUSING: alembic_version is in the truncate closure. That would make the next deploy re-run every migration.")

        print(f"Connected to : {database} on {server}:{port}")
        print("")
        print(f"{'Table':28} {'Rows':>10}")
        print("-" * 40)
        total = 0
        for table in tables:
            c.execute(f"SELECT count(*) FROM {table}")
            count = c.fetchone()[0]
            total += count
            marker = "  <- root" if table in ROOTS else ""
            print(f"{table:28} {count:10}{marker}")
        print("-" * 40)
        print(f"{'total':28} {total:10}")

        # Bound to the connected server, not a constant: this is the whole
        # safety mechanism. A token obtained from the dev tunnel will not
        # match a prod one.
        token = "TRUNCATE_" + re.sub(r"[^A-Za-z0-9]+", "_", f"{database}_{server}")

        if not APPLY:
            print("")
            print("Dry run. Nothing was written.")
            print("Every table above will be EMPTIED, including any not named as a root")
            print("-- they are reached through foreign keys (meetings among them).")
            print("")
            print("If, and only if, that is the dev database, apply with:")
            print(f"  .\\truncate-dev.ps1 -Apply -Confirmation {token}")
            sys.exit(0)

        if GIVEN != token:
            sys.exit(
                "REFUSING: -Confirmation does not match this server.\n"
                f"  given:    {GIVEN or '<none>'}\n"
                f"  expected: {token}\n"
                "Re-run without -Apply against the database you intend to empty, and use the token it prints."
            )

        joined = ", ".join(ROOTS)
        print("")
        print(f"Truncating {joined} CASCADE ...")
        c.execute(f"TRUNCATE {joined} CASCADE")
        conn.commit()

        print("")
        print(f"{'Table':28} {'Rows':>10}")
        print("-" * 40)
        for table in tables:
            c.execute(f"SELECT count(*) FROM {table}")
            print(f"{table:28} {c.fetchone()[0]:10}")
        print("")
        print("Done. The dev database is empty; create test data with /add-seller and")
        print("/add-buyer, which stamp is_test = true in SOURCE Attio.")
'@ | py -
if ($LASTEXITCODE -ne 0) { throw "truncate-dev failed with exit code $LASTEXITCODE." }
} finally {
  Remove-Item Env:\WUSOOL_TRUNCATE_DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_TRUNCATE_APPLY -ErrorAction SilentlyContinue
  Remove-Item Env:\WUSOOL_TRUNCATE_CONFIRMATION -ErrorAction SilentlyContinue
}
