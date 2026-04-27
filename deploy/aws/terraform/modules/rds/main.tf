resource "aws_db_subnet_group" "main" {
  name       = var.app_name
  subnet_ids = var.subnet_ids

  tags = { Name = var.app_name }
}

resource "aws_db_instance" "main" {
  identifier = var.app_name

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_sg_id]

  publicly_accessible       = false
  multi_az                  = false
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.app_name}-final-snapshot"

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = { Name = var.app_name }

  lifecycle {
    # Prevent Terraform from re-applying a password rotation done outside Terraform.
    ignore_changes = [password]
  }
}
