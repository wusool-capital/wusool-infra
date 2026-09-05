#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

usage() {
  echo "usage: $0 [all|quality|unit|schema|integration|shell]" >&2
}

setup() {
  uv sync --locked --dev
  export DATABASE_URL="${DATABASE_URL:-postgresql://user:pass@localhost:15432/wusool_crm}"
  export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-xoxb-test-token}"
  export SLACK_SIGNING_SECRET="${SLACK_SIGNING_SECRET:-test-signing-secret}"
}

require_database() {
  if [[ -z "${CHECKS_DATABASE_URL:-}" ]]; then
    echo "CHECKS_DATABASE_URL must name a disposable Postgres database" >&2
    exit 64
  fi
  export DATABASE_URL="$CHECKS_DATABASE_URL"
}

quality() {
  uv run ruff check .
  uv run ruff format --check .
  uv run ty check .
}

unit() {
  uv run pytest --ignore-glob='*/tests/integration/*'
}

schema() {
  check_migration_graph
  require_database
  uv run alembic upgrade head
  uv run alembic check
}

check_migration_graph() {
  local heads
  heads="$(uv run alembic heads)"
  if [[ "$(grep -c '(head)' <<<"$heads")" -ne 1 ]]; then
    echo "Alembic migration graph must resolve to exactly one head:" >&2
    echo "$heads" >&2
    return 1
  fi
  uv run alembic history >/dev/null
}

integration() {
  require_database
  uv run alembic upgrade head
  uv run pytest \
    app/modules/ddl_commands/tests/integration \
    app/modules/matching_engine/tests/integration \
    tests/integration
}

shell() {
  bash ../.github/scripts/tests/test-nightly-attio-resync.sh
}

main() {
  local mode="${1:-all}"
  case "$mode" in
    all|quality|unit|schema|integration|shell) ;;
    *) usage; exit 64 ;;
  esac
  setup
  case "$mode" in
    all)
      quality
      unit
      schema
      integration
      shell
      ;;
    quality) quality ;;
    unit) unit ;;
    schema) schema ;;
    integration) integration ;;
    shell) shell ;;
  esac
}

main "$@"
