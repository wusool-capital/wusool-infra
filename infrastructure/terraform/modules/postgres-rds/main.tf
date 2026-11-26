resource "aws_security_group" "this" {
  name        = "${var.project}-${var.environment}-postgres"
  description = "Private PostgreSQL access for ${var.project} ${var.environment}"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = toset(var.allowed_security_group_ids)
    content {
      description     = "PostgreSQL from approved application security group"
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [ingress.value]
    }
  }

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-${var.environment}-postgres-sg"
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.project}-${var.environment}-postgres"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.project}-${var.environment}-postgres"
  }
}

# Only when pg_cron is wanted, so an environment without it keeps the default group.
resource "aws_db_parameter_group" "this" {
  count = var.enable_pg_cron ? 1 : 0

  name   = "${var.project}-${var.environment}-postgres${split(".", var.engine_version)[0]}"
  family = "postgres${split(".", var.engine_version)[0]}"

  # Keeps the RDS defaults (pg_stat_statements, pg_tle) and adds pg_cron.
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements,pg_tle,pg_cron"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "cron.database_name"
    value        = var.db_name
    apply_method = "pending-reboot"
  }

  # The family changes with the major version, which forces a new group.
  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project}-${var.environment}-postgres${split(".", var.engine_version)[0]}"
  }
}

resource "aws_db_instance" "this" {
  identifier = "${var.project}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allow_major_version_upgrade = var.allow_major_version_upgrade
  parameter_group_name        = try(aws_db_parameter_group.this[0].name, null)

  allocated_storage     = var.allocated_storage
  max_allocated_storage = max(var.allocated_storage, 100)
  storage_type          = "gp3"
  storage_encrypted     = true

  # When restoring from a snapshot the database name and master username come
  # from the snapshot itself; passing them is rejected by RDS.
  snapshot_identifier = var.snapshot_identifier
  db_name             = var.snapshot_identifier == null ? var.db_name : null
  username            = var.snapshot_identifier == null ? var.master_username : null

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  publicly_accessible    = false

  backup_retention_period   = var.backup_retention_period
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.project}-${var.environment}-postgres-final"

  apply_immediately = var.apply_immediately

  tags = {
    Name = "${var.project}-${var.environment}-postgres"
  }

  lifecycle {
    # A later change to snapshot_identifier would REPLACE the instance and
    # destroy its data. The seed only matters at creation time.
    ignore_changes = [snapshot_identifier]
  }
}
