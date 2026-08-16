# AMI is pinned via var.ami_id (H1) — deliberately NOT a `most_recent = true`
# lookup. That pattern resolved a new value on every plan while
# `ignore_changes = [ami]` on the instance hid it, meaning AMI upgrades were
# silently impossible to review and the instance was frozen indefinitely with
# no visible diff. An explicit pin makes an AMI change a normal, reviewable
# tfvars edit. `ignore_changes = [ami]` stays on the instance as
# belt-and-braces until H2 (n8n -> Postgres) makes the instance disposable.

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
  # just per app instead of a single pair of locals.
  apps_resolved = [for a in var.apps : {
    name = a.name
    # Bash variable names can't contain hyphens (app names can, e.g.
    # "toolkit") — this is used only for shell variable naming in
    # user_data.sh.tpl, never for docker-compose/Caddy/log identifiers.
    slug          = replace(a.name, "-", "_")
    image         = a.image
    app_secret_id = a.app_secret_id
    hostname      = a.public_url != "" ? regex("^https?://([^/]+)", a.public_url)[0] : "${a.name}-${local.generated_ip_label}.sslip.io"
    url           = a.public_url != "" ? a.public_url : "https://${a.name}-${local.generated_ip_label}.sslip.io"
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

  user_data_rendered = replace(templatefile("${path.module}/user_data.sh.tpl", {
    apps                    = local.apps_resolved
    ecr_registry            = local.ecr_registry
    aws_region              = var.aws_region
    cloudwatch_agent_config = local.cloudwatch_agent_config
  }), "\r\n", "\n")
}

resource "aws_instance" "wusool_toolkit" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.wusool_toolkit.id]
  key_name               = var.key_name != "" ? var.key_name : null
  iam_instance_profile   = aws_iam_instance_profile.wusool_toolkit.name

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = local.user_data_rendered

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  lifecycle {
    ignore_changes = [ami]
  }

  tags = {
    Name = "${var.project}-${var.environment}-toolkit"
  }
}

resource "aws_eip_association" "wusool_toolkit" {
  instance_id   = aws_instance.wusool_toolkit.id
  allocation_id = aws_eip.wusool_toolkit.id
}

# Existing instances do not rerun EC2 user data when it changes. This SSM
# association applies the same idempotent bootstrap (docker login, pull the
# pinned digest, restart) without replacing the instance, so a redeploy is
# `terraform apply` followed by this association re-running — no manual SSH
# step required.
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
    key    = "InstanceIds"
    values = [aws_instance.wusool_toolkit.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy_attachment.cloudwatch,
    aws_eip_association.wusool_toolkit
  ]
}

resource "aws_cloudwatch_metric_alarm" "status" {
  alarm_name          = "${var.project}-${var.environment}-toolkit-status-check"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { InstanceId = aws_instance.wusool_toolkit.id }
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
  dimensions          = { InstanceId = aws_instance.wusool_toolkit.id }
}
