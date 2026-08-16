# AMI is pinned via var.ami_id (H1) — deliberately NOT a `most_recent = true`
# lookup. That pattern resolved a new value on every plan while
# `ignore_changes = [ami]` on the instance hid it, meaning AMI upgrades were
# silently impossible to review and the instance was frozen indefinitely with
# no visible diff. An explicit pin makes an AMI change a normal, reviewable
# tfvars edit. `ignore_changes = [ami]` stays on the instance as
# belt-and-braces until H2 (n8n -> Postgres) makes the instance disposable.

resource "aws_security_group" "n8n" {
  name        = "${var.project}-${var.environment}-n8n"
  description = "Security group for the n8n EC2 instance"
  vpc_id      = var.vpc_id

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
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.web_cidr_blocks
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.web_cidr_blocks
  }

  dynamic "ingress" {
    for_each = var.expose_n8n_port ? [1] : []
    content {
      description = "n8n UI (temporary until reverse proxy is configured)"
      from_port   = 5678
      to_port     = 5678
      protocol    = "tcp"
      cidr_blocks = var.web_cidr_blocks
    }
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-${var.environment}-n8n-sg"
  }
}

resource "aws_iam_role" "n8n" {
  name = "${var.project}-${var.environment}-n8n-ec2"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.n8n.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.n8n.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "secrets_manager" {
  count = length(var.secrets_manager_secret_arns) > 0 ? 1 : 0

  name = "${var.project}-${var.environment}-n8n-secrets-manager"
  role = aws_iam_role.n8n.id

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

resource "aws_iam_instance_profile" "n8n" {
  name = "${var.project}-${var.environment}-n8n"
  role = aws_iam_role.n8n.name
}

resource "aws_cloudwatch_log_group" "n8n" {
  name              = "/${var.project}/${var.environment}/n8n"
  retention_in_days = 30
}

resource "aws_eip" "n8n" {
  domain = "vpc"

  tags = { Name = "${var.project}-${var.environment}-n8n-eip" }
}

locals {
  generated_hostname = "${replace(aws_eip.n8n.public_ip, ".", "-")}.sslip.io"
  public_hostname    = var.n8n_webhook_url != "" ? regex("^https?://([^/]+)", var.n8n_webhook_url)[0] : local.generated_hostname
  webhook_url        = var.n8n_webhook_url != "" ? var.n8n_webhook_url : "https://${local.public_hostname}/"
  alarm_actions      = var.alarm_topic_arn != "" ? [var.alarm_topic_arn] : []

  # Caddy serves the primary hostname plus any additional ones. Rendering all of
  # them is what keeps a domain cutover from dropping the old host.
  all_hostnames   = distinct(concat([local.public_hostname], var.additional_hostnames))
  caddy_hostnames = join(", ", local.all_hostnames)

  # Rendered ONCE and reused by both aws_instance.user_data and
  # aws_ssm_document.bootstrap. Previously templatefile() was called twice with
  # the same inputs — two places to drift, which is how the registered document
  # went stale against the template.
  user_data_rendered = replace(templatefile("${path.module}/user_data.sh.tpl", {
    n8n_webhook_url = local.webhook_url
    n8n_timezone    = var.n8n_timezone
    public_hostname = local.public_hostname
    caddy_hostnames = local.caddy_hostnames
    log_group_name  = aws_cloudwatch_log_group.n8n.name
    n8n_secret_id   = var.n8n_secret_id
    n8n_image       = var.n8n_image
    runners_image   = var.runners_image
    caddy_image     = var.caddy_image
  }), "\r\n", "\n")
}

resource "aws_instance" "n8n" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.n8n.id]
  key_name               = var.key_name != "" ? var.key_name : null
  iam_instance_profile   = aws_iam_instance_profile.n8n.name

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
    Name = "${var.project}-${var.environment}-n8n"
  }
}

resource "aws_eip_association" "n8n" {
  instance_id   = aws_instance.n8n.id
  allocation_id = aws_eip.n8n.id
}

# Existing instances do not rerun EC2 user data when it changes. This SSM
# association applies the same idempotent bootstrap without replacing the
# instance (and therefore preserves the n8n Docker volume).
resource "aws_ssm_document" "bootstrap" {
  name            = "${var.project}-${var.environment}-n8n-bootstrap"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Install and configure n8n, Caddy, and CloudWatch Agent"
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "bootstrap"
      inputs = {
        timeoutSeconds = "1800"
        runCommand = [
          "echo '${base64encode(local.user_data_rendered)}' | base64 -d > /tmp/${var.project}-n8n-bootstrap.sh",
          "chmod 700 /tmp/${var.project}-n8n-bootstrap.sh",
          "sudo bash /tmp/${var.project}-n8n-bootstrap.sh"
        ]
      }
    }]
  })
}

resource "aws_ssm_association" "bootstrap" {
  name             = aws_ssm_document.bootstrap.name
  association_name = "${var.project}-${var.environment}-n8n-bootstrap"

  targets {
    key    = "InstanceIds"
    values = [aws_instance.n8n.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy_attachment.cloudwatch,
    aws_eip_association.n8n
  ]
}

resource "aws_cloudwatch_metric_alarm" "status" {
  alarm_name          = "${var.project}-${var.environment}-n8n-status-check"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { InstanceId = aws_instance.n8n.id }
}

resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.project}-${var.environment}-n8n-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { InstanceId = aws_instance.n8n.id }
}
