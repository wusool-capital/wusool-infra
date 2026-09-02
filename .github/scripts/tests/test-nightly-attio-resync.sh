#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="$SCRIPT_DIR/../nightly-attio-resync.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/aws" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${AWS_CALLS_FILE:?}"
case "$1 $2" in
  "ssm describe-instance-information") printf 'Online\n' ;;
  "ssm send-command") printf 'cmd-123\n' ;;
  "ssm get-command-invocation")
    if [[ "$*" == *"--query Status"* ]]; then printf 'Success\n';
    elif [[ "$*" == *"StandardOutputContent"* ]]; then printf 'sync output\n';
    else printf 'sync error\n'; fi
    ;;
esac
EOF
chmod +x "$TMP/aws"

export PATH="$TMP:$PATH"
export AWS_CALLS_FILE="$TMP/calls"
export NIGHTLY_SYNC_SLEEP=0

"$SCRIPT" i-123 42 /wusool/dev/toolkit

grep -q 'ssm describe-instance-information' "$AWS_CALLS_FILE"
grep -q 'ssm send-command' "$AWS_CALLS_FILE"
grep -q 'CloudWatchOutput' "$AWS_CALLS_FILE"
grep -q 'memory' "$AWS_CALLS_FILE"
grep -q 'toolkit-nightly-attio-resync' "$AWS_CALLS_FILE"
grep -q 'docker ps -a' "$AWS_CALLS_FILE"
grep -q 'executionTimeout' "$AWS_CALLS_FILE"
grep -q 'timeout-seconds 120' "$AWS_CALLS_FILE"

echo 'nightly workflow orchestration test passed'
