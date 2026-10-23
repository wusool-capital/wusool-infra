#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="$SCRIPT_DIR/../find-toolkit-instance.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/aws" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  ec2) [[ -n "${FAKE_EC2_FAIL:-}" ]] && { echo "AccessDenied" >&2; exit 254; }
       printf '%s\n' "${FAKE_IID:-None}" ;;
  autoscaling) printf '%s\n' "${FAKE_ASG:-}" ;;
esac
EOF
chmod +x "$TMP/aws"
export PATH="$TMP:$PATH"

# Running instance: its ID is printed.
[[ "$(FAKE_IID=i-123 "$SCRIPT" prod)" == i-123 ]]

# No instance and no ASG (create_instance = false): empty, success.
[[ -z "$("$SCRIPT" prod)" ]]

# No instance but the ASG exists (mid-replacement): fails, never empty-success.
if FAKE_ASG=wusool-prod-toolkit-abc "$SCRIPT" prod 2>/dev/null; then
  echo "expected failure when the ASG has no running instance" >&2
  exit 1
fi

# An AWS error fails instead of reading as "no instance".
if FAKE_EC2_FAIL=1 "$SCRIPT" prod 2>/dev/null; then
  echo "expected failure on an AWS error" >&2
  exit 1
fi

echo 'find-toolkit-instance test passed'
