variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "db_username" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "spa_origin" { type = string }

resource "aws_s3_bucket" "files" {
  bucket_prefix = "${var.project_name}-${var.environment}-files-"
  force_destroy = var.environment != "prod"
  tags = {
    Name = "${var.project_name}-${var.environment}-files"
  }
}

resource "aws_s3_bucket_public_access_block" "files" {
  bucket                  = aws_s3_bucket.files.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "files" {
  bucket = aws_s3_bucket.files.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "HEAD"]
    allowed_origins = [var.spa_origin]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.project_name}-${var.environment}-jobs"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
}

resource "aws_security_group" "db" {
  name   = "${var.project_name}-${var.environment}-db"
  vpc_id = var.vpc_id
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier                 = "${var.project_name}-${var.environment}"
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = "db.t4g.micro"
  allocated_storage          = 20
  username                   = var.db_username
  password                   = var.db_password
  db_subnet_group_name       = aws_db_subnet_group.main.name
  vpc_security_group_ids     = [aws_security_group.db.id]
  skip_final_snapshot        = var.environment != "prod"
  publicly_accessible        = false
  backup_retention_period    = var.environment == "prod" ? 7 : 1
  deletion_protection        = var.environment == "prod"
}

output "s3_bucket_name" {
  value = aws_s3_bucket.files.bucket
}

output "sqs_queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "db_endpoint" {
  value = aws_db_instance.postgres.address
}
