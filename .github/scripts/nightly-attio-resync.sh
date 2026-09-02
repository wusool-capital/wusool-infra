#!/usr/bin/env bash
# Run the DEV toolkit nightly resync through SSM with bounded resources and
# observable, cancellable execution.
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 INSTANCE_ID RUN_ID CLOUDWATCH_LOG_GROUP" >&2
  exit 64
fi

IID=$1
RUN_ID=$2
LOG_GROUP=$3
POLL_INTERVAL=${NIGHTLY_SYNC_SLEEP:-15}
MAX_POLLS=100
CMD=''
FINISHED=0

cancel_command() {
  if [[ -n "$CMD" && "$FINISHED" -eq 0 ]]; then
    echo "Cancelling SSM command $CMD"
    aws ssm cancel-command --command-id "$CMD" >/dev/null 2>&1 || true
  fi
}
trap cancel_command EXIT
trap 'exit 143' INT TERM

PING=$(aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$IID" \
  --query 'InstanceInformationList[0].PingStatus' --output text 2>&1) || {
  echo "::error::Unable to query SSM agent status: $PING" >&2
  exit 1
}
if [[ "$PING" != Online ]]; then
  echo "::error::Toolkit instance $IID is not SSM-online (status: $PING)" >&2
  exit 1
fi

COMMANDS_JSON=$(jq -n \
  --arg image_cmd 'CID=$(docker ps -a --filter "name=^/toolkit$" --format "{{.ID}}" | head -1); test -n "$CID" || { echo "toolkit container does not exist" >&2; exit 1; }; IMAGE=$(docker inspect --format="{{.Image}}" "$CID"); test -n "$IMAGE" || { echo "could not resolve toolkit image from container $CID" >&2; exit 1; }' \
  --arg run_cmd 'test -z "$(docker ps --filter "name=^/toolkit-nightly-attio-resync$" --format "{{.ID}}")" || { echo "nightly resync already running" >&2; exit 75; }; timeout --signal=TERM --kill-after=30s 15m docker run --rm --name toolkit-nightly-attio-resync --memory=384m --memory-swap=384m --cpus=0.75 --env-file /opt/toolkit/toolkit/.env.production "$IMAGE" python -m ddl_commands.modules.attio_sync.full_resync' \
  '["set -Eeuo pipefail", $image_cmd, $run_cmd]')
PARAMETERS_JSON=$(jq -n --argjson commands "$COMMANDS_JSON" \
  '{commands: $commands, executionTimeout: ["1200"]}')

CMD=$(aws ssm send-command \
  --document-name AWS-RunShellScript \
  --instance-ids "$IID" \
  --comment "nightly attio full resync (run $RUN_ID)" \
  --timeout-seconds 120 \
  --parameters "$PARAMETERS_JSON" \
  --cloud-watch-output-config "CloudWatchOutputEnabled=true,CloudWatchLogGroupName=$LOG_GROUP" \
  --query Command.CommandId --output text)
echo "SSM command: $CMD"

STATUS=Pending
ERRS=0
for _ in $(seq 1 "$MAX_POLLS"); do
  if OUT=$(aws ssm get-command-invocation --command-id "$CMD" --instance-id "$IID" \
      --query Status --output text 2>&1); then
    ERRS=0
    STATUS=$OUT
  else
    ERRS=$((ERRS + 1))
    if (( ERRS >= 8 )); then
      echo "::error::SSM poll failed 8x in a row: $OUT" >&2
      cancel_command
      exit 1
    fi
  fi
  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut|DeliveryTimedOut|Delivery\ TimedOut|Cancelling|Undeliverable|Terminated) break ;;
  esac
  sleep "$POLL_INTERVAL"
done

if [[ "$STATUS" == Pending || "$STATUS" == InProgress || "$STATUS" == Delayed ]]; then
  echo "::error::SSM command did not finish within $((MAX_POLLS * POLL_INTERVAL)) seconds" >&2
  cancel_command
  exit 1
fi

echo '--- resync stdout ---'
aws ssm get-command-invocation --command-id "$CMD" --instance-id "$IID" \
  --query StandardOutputContent --output text || echo '(could not retrieve stdout)'
echo '--- resync stderr ---'
aws ssm get-command-invocation --command-id "$CMD" --instance-id "$IID" \
  --query StandardErrorContent --output text || echo '(could not retrieve stderr)'

if [[ "$STATUS" != Success ]]; then
  echo "::error::nightly full resync ended in status: $STATUS" >&2
  exit 1
fi
FINISHED=1
echo 'nightly full resync succeeded'
