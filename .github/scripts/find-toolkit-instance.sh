#!/usr/bin/env bash
# Prints the running toolkit instance ID; empty only when no toolkit ASG exists (create_instance = false).
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 ENVIRONMENT" >&2
  exit 64
fi
ENV=$1

IID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=wusool-$ENV-toolkit" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
if [[ -n "$IID" && "$IID" != None ]]; then
  echo "$IID"
  exit 0
fi

ASG=$(aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?starts_with(AutoScalingGroupName, 'wusool-$ENV-toolkit-')].AutoScalingGroupName" \
  --output text)
if [[ -n "$ASG" ]]; then
  echo "::error::Toolkit ASG $ASG has no running instance (likely mid-replacement). Re-run once it is back." >&2
  exit 1
fi
