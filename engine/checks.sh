#!/usr/bin/env bash
# Engine counterpart of client/checks.sh — the same gates CI runs.
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

usage() {
  echo "usage: $0 [all|quality|build]" >&2
}

setup() {
  npm ci --no-audit --no-fund
}

quality() {
  npm run typecheck
}

build() {
  npm run build
}

main() {
  local mode="${1:-all}"
  case "$mode" in
    all|quality|build) ;;
    *) usage; exit 64 ;;
  esac
  setup
  case "$mode" in
    all)
      quality
      build
      ;;
    quality) quality ;;
    build) build ;;
  esac
}

main "$@"
