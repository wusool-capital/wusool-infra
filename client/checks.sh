#!/usr/bin/env bash
# Client counterpart of server/checks.sh — the same gates CI runs.
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

usage() {
  echo "usage: $0 [all|quality|unit|api|build]" >&2
}

setup() {
  npm ci --no-audit --no-fund
}

quality() {
  npx tsr generate
  npm run typecheck
  npm run lint
  npm run format:check
}

unit() {
  npm test
}

# Fails when client/openapi.json or src/gen/ is out of date with the backend.
api() {
  (cd ../server && uv run python scripts/export_openapi.py ../client/openapi.json)
  npm run gen:api
  npx prettier --write openapi.json >/dev/null
  git diff --exit-code -- openapi.json src/gen
  if [[ -n "$(git status --porcelain -- openapi.json src/gen)" ]]; then
    echo "Untracked generated API files; run npm run gen:api and commit them" >&2
    return 1
  fi
}

build() {
  npm run build
}

main() {
  local mode="${1:-all}"
  case "$mode" in
    all|quality|unit|api|build) ;;
    *) usage; exit 64 ;;
  esac
  setup
  case "$mode" in
    all)
      quality
      unit
      api
      build
      ;;
    quality) quality ;;
    unit) unit ;;
    api) api ;;
    build) build ;;
  esac
}

main "$@"
