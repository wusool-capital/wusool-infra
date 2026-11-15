#!/usr/bin/env bash
# Engine counterpart of client/checks.sh — the same gates CI runs.
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

usage() {
  echo "usage: $0 [all|quality|api|build]" >&2
}

setup() {
  npm ci --no-audit --no-fund
}

quality() {
  npm run typecheck
}

# Fails when engine-frontend/openapi.json or app/gen/ is out of date with the backend.
api() {
  (cd ../server && uv run python scripts/export_openapi.py ../engine-frontend/openapi.json --app engine)
  npm run gen:api
  git diff --exit-code -- openapi.json app/gen
  if [[ -n "$(git status --porcelain -- openapi.json app/gen)" ]]; then
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
    all|quality|api|build) ;;
    *) usage; exit 64 ;;
  esac
  setup
  case "$mode" in
    all)
      quality
      api
      build
      ;;
    quality) quality ;;
    api) api ;;
    build) build ;;
  esac
}

main "$@"
