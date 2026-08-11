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

resource "aws_db_instance" "this" {
  identifier = "${var.project}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = max(var.allocated_storage, 100)
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.master_username

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  publicly_accessible    = false

  backup_retention_period   = var.backup_retention_period
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.project}-${var.environment}-postgres-final"

  apply_immediately = false

  tags = {
    Name = "${var.project}-${var.environment}-postgres"
  }
}
