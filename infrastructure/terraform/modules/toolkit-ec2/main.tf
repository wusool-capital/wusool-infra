# AMI is pinned via var.ami_id (H1) — deliberately NOT a `most_recent = true`
# lookup. That pattern resolved a new value on every plan while
# `ignore_changes = [ami]` on the instance hid it, meaning AMI upgrades were
# silently impossible to review and the instance was frozen indefinitely with
# no visible diff. An explicit pin makes an AMI change a normal, reviewable
# tfvars edit — which only works if `ignore_changes = [ami]` is actually
# removed from the instance (a prior pass fixed the AMI source but left this
# in place, quietly defeating the fix — caught in code review 2026-08-16).

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

data "aws_caller_identity" "current" {}

# aws_launch_template's block_device_mappings needs an explicit device_name —
# unlike aws_instance.root_block_device, it can't infer the root device from
# the AMI. Derived from the pinned AMI itself rather than hardcoded, so a
# future AMI change (var.ami_id is a deliberate, reviewed tfvars edit per the
# H1 comment above) can't silently attach root_volume_size/encryption to an
# unattached extra volume instead of the disk the instance actually boots
# from.
data "aws_ami" "wusool_toolkit" {
  filter {
    name   = "image-id"
    values = [var.ami_id]
  }
}

resource "aws_security_group" "wusool_toolkit" {
  # name_prefix, not name: a security group cannot be destroyed while an ENI
  # still uses it or another SG's rules reference it. With a fixed name and
  # default destroy-then-create ordering, renaming this SG deadlocks - the old
  # one cannot be deleted until the instance moves off it, and the instance
  # cannot move until the new one exists.
  name_prefix = "${var.project}-${var.environment}-toolkit-"
  description = "Security group for the wusool-toolkit EC2 instance"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  dynamic "ingress" {
    for_each = length(var.ssh_cidr_blocks) > 0 ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.ssh_cidr_blocks
    }
  }

  ingress {
    description = "HTTP (redirects to HTTPS via Caddy)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.web_cidr_blocks
  }

  ingress {
    description = "HTTPS (Slack Events API / interactivity Request URL)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.web_cidr_blocks
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-${var.environment}-toolkit-sg"
  }
}

resource "aws_iam_role" "wusool_toolkit" {
  name = "${var.project}-${var.environment}-toolkit-ec2"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.wusool_toolkit.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.wusool_toolkit.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# The instance is ASG-managed (below), so it no longer has a stable ID for a
# static aws_eip_association to target. Each new instance re-associates the
# one persistent EIP to itself on boot (user_data.sh.tpl) — this is the
# permission that lets it do so. Scoped to this one EIP allocation and to
# instances in this account/region (AssociateAddress's "instance" resource
# type has no further way to scope to "this ASG only" short of a tag
# condition, and the instance calling this only ever targets itself).
resource "aws_iam_role_policy" "eip_associate" {
  name = "${var.project}-${var.environment}-toolkit-eip-associate"
  role = aws_iam_role.wusool_toolkit.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ec2:AssociateAddress"]
      Resource = [
        "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:elastic-ip/${aws_eip.wusool_toolkit.id}",
        "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy" "secrets_manager" {
  count = length(var.secrets_manager_secret_arns) > 0 ? 1 : 0

  name = "${var.project}-${var.environment}-toolkit-secrets-manager"
  role = aws_iam_role.wusool_toolkit.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue"
      ]
      Resource = var.secrets_manager_secret_arns
    }]
  })
}

# GetAuthorizationToken is account-level (no resource scoping possible in IAM);
# the pull actions are scoped to just this environment's own ECR repo, not
# every repo in the account.
resource "aws_iam_role_policy" "ecr_pull" {
  name = "${var.project}-${var.environment}-toolkit-ecr-pull"
  role = aws_iam_role.wusool_toolkit.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "wusool_toolkit" {
  name = "${var.project}-${var.environment}-toolkit"
  role = aws_iam_role.wusool_toolkit.name
}

resource "aws_cloudwatch_log_group" "wusool_toolkit" {
  name              = "/${var.project}/${var.environment}/toolkit"
  retention_in_days = 30
}

resource "aws_eip" "wusool_toolkit" {
  domain = "vpc"

  tags = { Name = "${var.project}-${var.environment}-toolkit-eip" }
}

locals {
  generated_ip_label = replace(aws_eip.wusool_toolkit.public_ip, ".", "-")
  alarm_actions      = var.alarm_topic_arn != "" ? [var.alarm_topic_arn] : []

  # Per-app hostname/URL resolution — same sslip.io-fallback logic as before,
  # just per app instead of a single pair of locals. Hoisted out of
  # apps_resolved so the fallback ternary is written once, not once per
  # consumer.
  app_hostnames = { for a in var.apps : a.name =>
    a.public_url != "" ? regex("^https?://([^/]+)", a.public_url)[0] : "${a.name}-${local.generated_ip_label}.sslip.io"
  }

  apps_resolved = [for a in var.apps : {
    name = a.name
    # Bash variable names can't contain hyphens (app names can, e.g.
    # "toolkit") — this is used only for shell variable naming in
    # user_data.sh.tpl, never for docker-compose/Caddy/log identifiers.
    slug          = replace(a.name, "-", "_")
    image         = a.image
    app_secret_id = a.app_secret_id
    hostname      = local.app_hostnames[a.name]
    url           = a.public_url != "" ? a.public_url : "https://${local.app_hostnames[a.name]}"
    # Caddy accepts comma-separated site addresses on one block; every name
    # gets its own certificate and all of them proxy to the same container.
    site_addresses = join(", ", concat([local.app_hostnames[a.name]], a.extra_hostnames))
  }]

  # ECR registry host, derived from any app's image reference (everything
  # before the first "/"). Used to scope the docker login on the instance.
  ecr_registry = split("/", var.apps[0].image)[0]

  # Built with Terraform's own jsonencode() over an HCL list, not hand-joined
  # inside the bash template, so there's no comma-joining bug to introduce.
  cloudwatch_log_entries = concat(
    [{
      file_path       = "/var/log/cloud-init-output.log"
      log_group_name  = aws_cloudwatch_log_group.wusool_toolkit.name
      log_stream_name = "{instance_id}/cloud-init"
    }],
    [for app in local.apps_resolved : {
      file_path       = "/var/lib/docker/volumes/toolkit_caddy_data/_data/${app.name}-access.log"
      log_group_name  = aws_cloudwatch_log_group.wusool_toolkit.name
      log_stream_name = "{instance_id}/caddy-${app.name}"
    }]
  )
  cloudwatch_agent_config = jsonencode({
    logs = { logs_collected = { files = { collect_list = local.cloudwatch_log_entries } } }
  })

  # One SOURCE Attio workspace serves both environments; ATTIO_IS_TEST is the
  # only thing separating them, so it is derived from the environment rather
  # than being a second knob that can disagree with it. Only prod owns
  # production records.
  attio_is_test = var.environment == "prod" ? "false" : "true"

  user_data_rendered = replace(templatefile("${path.module}/user_data.sh.tpl", {
    apps                    = local.apps_resolved
    ecr_registry            = local.ecr_registry
    aws_region              = var.aws_region
    attio_is_test           = local.attio_is_test
    cloudwatch_agent_config = local.cloudwatch_agent_config
    cloudwatch_log_group    = aws_cloudwatch_log_group.wusool_toolkit.name
    eip_allocation_id       = aws_eip.wusool_toolkit.id
  }), "\r\n", "\n")
}

# Launch Template + ASG(1), not a standalone aws_instance: an ASG is what
# gives this a real self-healing property a lone instance has none of — if
# the instance is ever terminated (retirement, manual mistake, host failure),
# the ASG launches a replacement automatically. user_data re-associates the
# one persistent EIP to whichever instance boots, so the public IP/hostname
# never changes.
resource "aws_launch_template" "wusool_toolkit" {
  name_prefix   = "${var.project}-${var.environment}-toolkit-"
  image_id      = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name != "" ? var.key_name : null

  iam_instance_profile {
    name = aws_iam_instance_profile.wusool_toolkit.name
  }

  vpc_security_group_ids = [aws_security_group.wusool_toolkit.id]

  block_device_mappings {
    device_name = data.aws_ami.wusool_toolkit.root_device_name
    ebs {
      volume_size = var.root_volume_size
      volume_type = "gp3"
      encrypted   = true
    }
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  user_data = base64encode(local.user_data_rendered)

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project}-${var.environment}-toolkit"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "wusool_toolkit" {
  name_prefix         = "${var.project}-${var.environment}-toolkit-"
  min_size            = 1
  max_size            = 1
  desired_capacity    = 1
  vpc_zone_identifier = [var.subnet_id]

  # No load balancer attached, so this is AWS's own system/instance status
  # checks — not an app-level check. It replaces a terminated or
  # hardware-impaired instance; it does NOT see a hung-but-alive process
  # (that's the container-level healthcheck in user_data.sh.tpl) or a
  # network-path blip while the instance itself stays healthy (that's the
  # Route 53 health check below — visibility only, it can't act on this).
  health_check_type         = "EC2"
  health_check_grace_period = 120

  # Group metrics collection is OFF by default on every ASG — confirmed live
  # (2026-09-09): `list-metrics` returned zero AWS/AutoScaling datapoints for
  # this group at ANY capacity, not just zero instances. Combined with the
  # in_service alarm's treat_missing_data = "breaching" below, that meant the
  # alarm was permanently stuck in false ALARM the moment it was created —
  # not just during a genuine zero-instance drill, which is the only case it
  # was actually tested against. Without this, treat_missing_data ->
  # "breaching" turns "nobody enabled this metric" into "the alarm is always
  # lying", which is worse than the INSUFFICIENT_DATA gap it was meant to fix.
  enabled_metrics = ["GroupInServiceInstances"]

  launch_template {
    id      = aws_launch_template.wusool_toolkit.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.project}-${var.environment}-toolkit"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Existing instances do not rerun EC2 user data when it changes. This SSM
# association applies the same idempotent bootstrap (docker login, pull the
# pinned digest, restart) without replacing the instance, so a redeploy is
# `terraform apply` followed by this association re-running — no manual SSH
# step required. Tag-based targeting (not InstanceIds): the ASG can replace
# the underlying instance at any time, and this must keep applying to
# whichever one is currently running without a Terraform apply in between.
resource "aws_ssm_document" "bootstrap" {
  name            = "${var.project}-${var.environment}-toolkit-bootstrap"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy/redeploy the app(s) on this instance: docker login to ECR, pull the pinned digest, restart"
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "bootstrap"
      inputs = {
        timeoutSeconds = "1800"
        runCommand = [
          "echo '${base64encode(local.user_data_rendered)}' | base64 -d > /tmp/${var.project}-toolkit-bootstrap.sh",
          "chmod 700 /tmp/${var.project}-toolkit-bootstrap.sh",
          "sudo bash /tmp/${var.project}-toolkit-bootstrap.sh"
        ]
      }
    }]
  })
}

resource "aws_ssm_association" "bootstrap" {
  name             = aws_ssm_document.bootstrap.name
  association_name = "${var.project}-${var.environment}-toolkit-bootstrap"

  targets {
    key    = "tag:Name"
    values = ["${var.project}-${var.environment}-toolkit"]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy_attachment.cloudwatch,
    aws_autoscaling_group.wusool_toolkit,
  ]
}

# StatusCheckFailed/CPUUtilization pinned to a specific InstanceId (the old
# shape here) go stale the moment the ASG replaces the instance — a static
# dimension value doesn't follow rotation. AutoScalingGroupName is a stable
# dimension CloudWatch aggregates onto automatically for every instance the
# ASG currently owns, with no extra configuration.
resource "aws_cloudwatch_metric_alarm" "in_service" {
  alarm_name          = "${var.project}-${var.environment}-toolkit-not-in-service"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "GroupInServiceInstances"
  namespace           = "AWS/AutoScaling"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  # Confirmed by a live drill (2026-09-09, dev): with 0 in-service instances,
  # GroupInServiceInstances publishes NO datapoints at all — not even an
  # explicit 0. Without this, the default "missing" behavior leaves the
  # alarm stuck in INSUFFICIENT_DATA — no Slack alert, no signal of any
  # kind — for exactly the scenario this alarm exists to catch.
  treat_missing_data = "breaching"
  alarm_actions      = local.alarm_actions
  ok_actions         = local.alarm_actions
  dimensions         = { AutoScalingGroupName = aws_autoscaling_group.wusool_toolkit.name }
}

resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.project}-${var.environment}-toolkit-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { AutoScalingGroupName = aws_autoscaling_group.wusool_toolkit.name }
}

# External reachability check, run from outside AWS's network — the layer
# that catches a network-path blip while the instance itself stays healthy
# (confirmed against a real incident: 2026-09-09 prod, CPU flat, zero
# StatusCheckFailed, /health serving 200 throughout, yet a Slack request
# never reached the box at all). Visibility only: nothing here auto-heals a
# blip this short, it exists to make it visible instead of invisible.
#
# Targets /health, NOT /readiness: /readiness also fails on a pure database
# blip (server/main.py), which is a different, unrelated failure mode this
# alarm isn't meant to page on — it would misreport a DB hiccup as "the box
# is unreachable" when the network path is actually fine. /health is a pure
# liveness check with no DB dependency, so it isolates reachability the way
# this alarm's name promises.
resource "aws_route53_health_check" "wusool_toolkit" {
  for_each = { for app in local.apps_resolved : app.name => app }

  fqdn              = each.value.hostname
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30
  enable_sni        = true

  tags = { Name = "${var.project}-${var.environment}-${each.key}-reachability" }
}

# The ALARM itself must live in us-east-1 — that's not a choice, it's where
# Route 53 publishes HealthCheckStatus, full stop (AWS's own console
# instructions: "Route 53 metrics are not available if you select any other
# region"). The SNS target ALSO has to be us-east-1: a live apply
# (2026-09-09) proved this the hard way — PutMetricAlarm rejected an
# eu-central-1 action ARN on this alarm with "Invalid region eu-central-1
# specified. Only us-east-1 is supported.", contradicting the general
# PutMetricAlarm API docs (which show cross-region SNS actions with no
# stated restriction — apparently true for ordinary alarms, not this
# Route 53-sourced one). Hence the separate us_east_1_alarm_topic_arn,
# rather than reusing the shared eu-central-1 alarm_topic_arn every other
# alarm in this module uses.
resource "aws_cloudwatch_metric_alarm" "reachability" {
  for_each = aws_route53_health_check.wusool_toolkit
  provider = aws.us_east_1

  alarm_name          = "${var.project}-${var.environment}-${each.key}-unreachable"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = var.us_east_1_alarm_topic_arn != "" ? [var.us_east_1_alarm_topic_arn] : []
  ok_actions          = var.us_east_1_alarm_topic_arn != "" ? [var.us_east_1_alarm_topic_arn] : []
  dimensions          = { HealthCheckId = each.value.id }
}
