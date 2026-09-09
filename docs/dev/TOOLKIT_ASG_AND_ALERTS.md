# wusool-toolkit: ASG self-healing + Slack alerting

> **Audience:** whoever operates or debugs the toolkit instance. Not for
> GitBook — internal infra only. Everything below was verified live against
> AWS account `030179310793` (profile `wusool`), including three deliberate
> failure drills run against dev on 2026-09-09.

## Why this exists

`wusool-<env>-toolkit` used to be a single `aws_instance` on a bare Elastic
IP — nothing detected or replaced it if it went down. This surfaced as a
real incident: prod's `/add-buyer` failed with `operation_timeout`,
intermittent, self-resolving. Diagnosis found the instance was healthy the
whole time (flat CPU, zero `StatusCheckFailed`, `/health` returning 200
throughout) — the request most likely never reached the box at all, a
network-path blip with nothing watching for it.

ECS Express Mode was evaluated and rejected (forces an ALB per VPC, ~$27/mo,
no sharing across dev/prod without merging environments — a real isolation
risk given `ATTIO_IS_TEST` is the only thing separating dev/prod CRM
writes). The fix that shipped: keep EC2, add the three things that were
actually missing. Cost: **~$6/mo added, across both environments** —
`stacks/toolkit/main.tf`'s `aws_route53_health_check` + `stacks/base`'s
Chatbot relay are the only new billable resources.

## Architecture

```
Elastic IP (unchanged, same IP always)
   │  self-associates on boot (--allow-reassociation)
   ▼
Auto Scaling Group, min=max=desired=1  ← modules/toolkit-ec2/main.tf
   │
   ▼
EC2 instance
   ├─ toolkit container   (the app)
   ├─ caddy container     (TLS, reverse proxy — unchanged)
   └─ autoheal container  (watches Docker HEALTHCHECK, force-restarts)

Route 53 health check (us-east-1, hits /health from outside AWS)
   → CloudWatch alarm (us-east-1)
   → SNS topic (eu-central-1, cross-region subscription — see gotcha below)
   → AWS Chatbot → #infra-alerts
```

Three failure modes, three different mechanisms — **they do not overlap**:

| Failure | Detected by | Action | Real observed recovery time |
|---|---|---|---|
| Instance terminated/dead | AWS's own EC2 status checks (ASG `health_check_type = "EC2"`) | ASG launches a replacement, which self-associates the EIP on boot | **~3.5 min** (drilled 2026-09-09: terminated 12:50:36 UTC, `/health` 200 again at 12:54:09) |
| Process hung but instance alive | Docker `HEALTHCHECK` (30s interval, 3 retries) | `autoheal` container force-restarts the toolkit container | **under 1 min** (drilled: paused 12:49:xx, healthy again by 12:50:09 — much faster than the ~2-3 min textbook estimate) |
| Network-path blip, instance and process both fine | Route 53 health check, from outside AWS | **Alert only.** Nothing auto-heals this — see below. | N/A |

**The third row is the one that actually matches the original incident**, and
it is deliberately alert-only. A blip that short can't be "fixed" by
replacing an instance that was never actually unhealthy — the value here is
visibility, not remediation. If this fires often enough to be worth
automating, the next step is a Lambda that calls
`autoscaling:SetInstanceHealth` off this alarm — not built, because it adds
real Lambda-authoring/IAM surface and there's no evidence yet it's needed.

## Alarms (all five route to `#infra-alerts`)

| Alarm | Namespace / region | Fires when |
|---|---|---|
| `wusool-<env>-toolkit-not-in-service` | `AWS/AutoScaling`, eu-central-1 | ASG has 0 in-service instances |
| `wusool-<env>-toolkit-high-cpu` | `AWS/EC2`, eu-central-1 | Toolkit instance CPU > 85% for 3×5min |
| `wusool-<env>-toolkit-unreachable` | `AWS/Route53`, **us-east-1** | External `/health` check fails |
| `wusool-<env>-n8n-status-check` | `AWS/EC2`, eu-central-1 | n8n instance fails AWS status checks (pre-existing, untouched) |
| `wusool-<env>-n8n-high-cpu` | `AWS/EC2`, eu-central-1 | n8n instance CPU > 85% (pre-existing, untouched) |

All five notify the same per-environment SNS topic
(`stacks/base`'s `aws_sns_topic.alerts`), which is what Chatbot subscribes
to — nothing alarm-specific to configure when adding a sixth alarm later,
as long as it points its `alarm_actions` at `var.alarm_topic_arn` (or, for a
`us-east-1`-namespace alarm, `var.us_east_1_alarm_topic_arn`).

## Slack setup (AWS Chatbot)

- Workspace: **Azmora**, `T0BAE254789`. Channel: **#infra-alerts**,
  `C0C0E16U0HH`.
- The Slack↔AWS Chatbot authorization is a **one-time manual step in the AWS
  Console** — Terraform cannot do this part (no API for it, only a
  browser-based Slack OAuth redirect). Already done; if it's ever lost,
  redo it at the [AWS Chatbot console](https://console.aws.amazon.com/chatbot/)
  → **Configure new client** → Slack → sign in → Allow.
- Everything else (the channel configuration resource, its IAM role, both
  SNS topics) is Terraform-managed in `stacks/base/main.tf`.

### Gotcha: Route 53 alarms need *everything* in us-east-1, not just the alarm

`AWS/Route53` alarms only exist in us-east-1 — that part is documented
(AWS's own console instructions: "Route 53 metrics are not available if
you select any other region"). What's **not** documented, and cost a failed
production apply to discover: the alarm's `alarm_actions` SNS target must
*also* be us-east-1. `PutMetricAlarm`'s own API docs show cross-region SNS
actions with no stated restriction, and that's true for ordinary alarms —
just not for this one. The error, verbatim:

```
Error: creating CloudWatch Metric Alarm (wusool-dev-toolkit-unreachable):
ValidationError: Invalid region eu-central-1 specified. Only us-east-1 is
supported.
```

### Gotcha: one Chatbot config per Slack channel per AWS account, full stop

The natural fix for the above — a second, us-east-1-local Chatbot channel
configuration for the same `#infra-alerts` channel — is also rejected:

```
InvalidRequestException: Slack channel with ID C0C0E16U0HH in Slack team
T0BAE254789 has already been configured for AWS account 030179310793.
```

Cross-region topic subscription on the *existing* config is one half of the
fix (Chatbot's `sns_topic_arns` list happily accepts a cross-region ARN).
The other half took a second failure to find: **this restriction is
account-wide, not per-environment either.** Dev and prod share this AWS
account, and both want `#infra-alerts` — dev's own per-environment config
(originally in `stacks/base`) applied first and succeeded, so prod's
identical attempt hit the exact same error, cross-environment this time.

The actual, final shape: the one Chatbot channel configuration + its IAM
role live in `stacks/account` (not per-environment `stacks/base` at all),
reading both environments' alerts topics via `terraform_remote_state` and
subscribing to all four — dev + prod, each in eu-central-1 and us-east-1.
`stacks/base` still creates its own per-environment SNS topics; only the
Chatbot-specific resources moved out.

### Gotcha: ASG group metrics collection is off by default — always, not just at zero instances

The first fix here (`treat_missing_data = "breaching"`) was based on an
incomplete diagnosis. It was verified against a real drill (desired
capacity → 0) and looked right: the alarm correctly went to `ALARM`. But a
few minutes after restoring capacity to a perfectly healthy instance, the
alarm was still stuck in `ALARM` — `aws cloudwatch list-metrics --namespace
AWS/AutoScaling` returned **zero metrics for this ASG, at any capacity**.
`aws_autoscaling_group.EnabledMetrics` was `[]`.

**Group metrics collection is an opt-in AWS setting, off by default on
every ASG.** Without it, `GroupInServiceInstances` (and every other
`AWS/AutoScaling` group metric) never publishes at all — not "zero
datapoints when the group is empty," but zero datapoints, ever, healthy or
not. `treat_missing_data = "breaching"` turned "nobody enabled this metric"
into "the alarm always lies," which is worse than the `INSUFFICIENT_DATA`
gap it was meant to close.

The real fix is `enabled_metrics = ["GroupInServiceInstances"]` on the
`aws_autoscaling_group` resource — an in-place update, no instance
replacement, confirmed live on both dev and prod. `treat_missing_data =
"breaching"` is still correct and still needed as the belt-and-suspenders
case (a metrics-collection outage, or the ASG being deleted outright), but
it only does its job once real data is flowing the rest of the time. If you
add a similar count-based ASG alarm elsewhere, check
`describe-auto-scaling-groups`'s `EnabledMetrics` first — don't assume a
missing-data setting alone makes the alarm trustworthy.

### How Slack threading actually works (and why you might miss an alert)

AWS Chatbot posts the **first** notification for a given alarm as a
top-level message, and every subsequent state change for that *same* alarm
threads as a reply underneath it — confirmed by watching
`wusool-dev-toolkit-unreachable` cycle OK→ALARM→OK twice in one afternoon,
all threading under the original message. There is **no setting** to
disable this (checked the Terraform resource schema and the official docs —
nothing). A *different* alarm firing gets its own separate top-level
message and its own thread.

This matters because Slack's default "All new messages" channel
notification preference **does not** include thread replies you're not
already part of — you can genuinely miss an ALARM transition sitting inside
a thread you never opened. Fix, once per person, no infra change:

1. `#infra-alerts` → channel name → **Notifications**
2. **More notification options**
3. Check **"Get notified about all replies and show them in your Threads
   view"**
4. Save

The alternative (a custom Lambda relay that posts fresh top-level messages
every time, no threading) was considered and rejected — it trades Chatbot's
zero-maintenance relay for a Lambda you'd own, webhook URL included, to fix
something a one-time Slack setting already fixes for free.

## Running the drills yourself

All three were run against dev on 2026-09-09. Numbers above are from that
run; your mileage may vary slightly.

**1. Kill the process without killing the container** (tests autoheal).
`kill -STOP` **does not work** on a container's PID 1 — this is a real
Linux kernel behavior
([`pid_namespaces(7)`](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)):
a PID namespace's init process only receives signals it has installed a
handler for, and SIGSTOP can't have a handler installed, so the kernel
silently discards it. Confirmed empirically: `kill -STOP 1` reports success
(`exit=0`) and the process stays in state `S` (sleeping), never `T`
(stopped), even checked immediately in the same command. Use `docker pause`
from the **host** instead — the cgroup freezer operates below that
protection layer entirely:

```bash
IID=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=wusool-dev-toolkit" \
  "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm send-command --document-name AWS-RunShellScript --instance-ids "$IID" \
  --parameters commands='["docker pause toolkit-toolkit-1"]'
```

Watch `docker inspect --format='{{.State.Health.Status}}' toolkit-toolkit-1`
transition to `unhealthy` and then see a fresh `StartedAt` timestamp once
autoheal restarts it. No need to manually unpause — `docker restart`
handles that.

**2. Terminate the instance** (tests ASG replacement + EIP re-association):

```bash
aws ec2 terminate-instances --instance-ids "$IID"
```

Watch `aws autoscaling describe-auto-scaling-groups` for the new instance
to reach `InService`, then confirm the EIP followed it:
`aws ec2 describe-addresses --allocation-ids eipalloc-08a05837701cffd64
--query 'Addresses[0].InstanceId'` should show the *new* instance ID within
a few minutes of it going `InService` (user_data associates it early in the
boot script, well before docker/compose finishes).

**3. Zero the ASG's desired capacity** (tests the `not-in-service` alarm —
real downtime for the whole drill, restore promptly):

```bash
ASG=$(aws autoscaling describe-auto-scaling-groups \
  --query 'AutoScalingGroups[?contains(AutoScalingGroupName,`wusool-dev-toolkit`)].AutoScalingGroupName' --output text)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$ASG" --min-size 0 --desired-capacity 0
# watch the alarm, then:
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$ASG" --min-size 1 --desired-capacity 1
```

⚠️ Min size has to drop to 0 too, not just desired — the ASG won't let
desired go below min.

## Finding the current instance (no more static `instance_id` output)

The instance is ASG-managed and can be replaced independent of any
`tofu apply`, so there's no stable Terraform output for it anymore. CI uses
`.github/actions/find-toolkit-instance`; do the same by hand:

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=wusool-<env>-toolkit" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text
```

`tofu output redeploy_command` (in `stacks/toolkit`) already wraps this
lookup into a one-liner that finds the instance and re-invokes the
bootstrap SSM document in one go.
