data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-${var.ami_architecture}"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = [var.ami_architecture]
  }
}

resource "aws_security_group" "matching_engine" {
  name        = "${var.project}-${var.environment}-matching-engine"
  description = "Security group for the matching-engine EC2 instance"
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
    Name = "${var.project}-${var.environment}-matching-engine-sg"
  }
}

resource "aws_iam_role" "matching_engine" {
  name = "${var.project}-${var.environment}-matching-engine-ec2"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.matching_engine.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.matching_engine.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "secrets_manager" {
  count = length(var.secrets_manager_secret_arns) > 0 ? 1 : 0

  name = "${var.project}-${var.environment}-matching-engine-secrets-manager"
  role = aws_iam_role.matching_engine.id

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

resource "aws_iam_instance_profile" "matching_engine" {
  name = "${var.project}-${var.environment}-matching-engine"
  role = aws_iam_role.matching_engine.name
}

resource "aws_cloudwatch_log_group" "matching_engine" {
  name              = "/${var.project}/${var.environment}/matching-engine"
  retention_in_days = 30
}

resource "aws_eip" "matching_engine" {
  domain = "vpc"

  tags = { Name = "${var.project}-${var.environment}-matching-engine-eip" }
}

locals {
  generated_hostname = "${replace(aws_eip.matching_engine.public_ip, ".", "-")}.sslip.io"
  public_hostname    = var.app_public_url != "" ? regex("^https?://([^/]+)", var.app_public_url)[0] : local.generated_hostname
  public_url         = var.app_public_url != "" ? var.app_public_url : "https://${local.public_hostname}"
  alarm_actions      = var.alarm_topic_arn != "" ? [var.alarm_topic_arn] : []

  user_data_rendered = replace(templatefile("${path.module}/user_data.sh.tpl", {
    public_hostname = local.public_hostname
    git_repo_url    = var.git_repo_url
    git_ref         = var.git_ref
    app_subdir      = var.app_subdir
    app_secret_id   = var.app_secret_id
    aws_region      = var.aws_region
    log_group_name  = aws_cloudwatch_log_group.matching_engine.name
  }), "\r\n", "\n")
}

resource "aws_instance" "matching_engine" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.matching_engine.id]
  key_name               = var.key_name != "" ? var.key_name : null
  iam_instance_profile   = aws_iam_instance_profile.matching_engine.name

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
    Name = "${var.project}-${var.environment}-matching-engine"
  }
}

resource "aws_eip_association" "matching_engine" {
  instance_id   = aws_instance.matching_engine.id
  allocation_id = aws_eip.matching_engine.id
}

# Existing instances do not rerun EC2 user data when it changes. This SSM
# association applies the same idempotent bootstrap (git pull, rebuild,
# restart) without replacing the instance, so a redeploy is `terraform apply`
# followed by this association re-running — no manual SSH step required.
resource "aws_ssm_document" "bootstrap" {
  name            = "${var.project}-${var.environment}-matching-engine-bootstrap"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy/redeploy the matching-engine app: git pull, docker compose build, restart"
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "bootstrap"
      inputs = {
        timeoutSeconds = "1800"
        runCommand = [
          "echo '${base64encode(local.user_data_rendered)}' | base64 -d > /tmp/${var.project}-matching-engine-bootstrap.sh",
          "chmod 700 /tmp/${var.project}-matching-engine-bootstrap.sh",
          "sudo bash /tmp/${var.project}-matching-engine-bootstrap.sh"
        ]
      }
    }]
  })
}

resource "aws_ssm_association" "bootstrap" {
  name             = aws_ssm_document.bootstrap.name
  association_name = "${var.project}-${var.environment}-matching-engine-bootstrap"

  targets {
    key    = "InstanceIds"
    values = [aws_instance.matching_engine.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy_attachment.cloudwatch,
    aws_eip_association.matching_engine
  ]
}

resource "aws_cloudwatch_metric_alarm" "status" {
  alarm_name          = "${var.project}-${var.environment}-matching-engine-status-check"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { InstanceId = aws_instance.matching_engine.id }
}

resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.project}-${var.environment}-matching-engine-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { InstanceId = aws_instance.matching_engine.id }
}
