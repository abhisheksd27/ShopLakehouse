variable "name" {
  type = string
}
variable "production" {
  type = bool
}
variable "database_subnets" {
  type = list(string)
}
variable "database_security_group" {
  type = string
}
variable "db_instance_class" {
  type = string
}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
resource "aws_kms_key" "lake" {
  description             = format("%s lake and database encryption", var.name)
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_kms_alias" "lake" {
  name          = format("alias/%s", var.name)
  target_key_id = aws_kms_key.lake.key_id
}
resource "aws_s3_bucket" "lake" {
  bucket        = format("%s-%s-lake", var.name, data.aws_caller_identity.current.account_id)
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.lake.arn
    }
    bucket_key_enabled = true
  }
}
resource "aws_s3_bucket_policy" "lake" {
  bucket = aws_s3_bucket.lake.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "s3:*",
      Resource  = [aws_s3_bucket.lake.arn, format("%s/*", aws_s3_bucket.lake.arn)],
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {
      prefix = ""
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  rule {
    id     = "expire-query-results"
    status = "Enabled"
    filter {
      prefix = "athena-results/"
    }
    expiration {
      days = 14
    }
    noncurrent_version_expiration {
      noncurrent_days = 14
    }
  }
}
resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.database_subnets
}
resource "aws_db_instance" "source" {
  identifier                      = var.name
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = var.db_instance_class
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.lake.arn
  db_name                         = "shoplakehouse"
  username                        = "shop_admin"
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [var.database_security_group]
  publicly_accessible             = false
  multi_az                        = var.production
  backup_retention_period         = var.production ? 14 : 7
  deletion_protection             = var.production
  skip_final_snapshot             = !var.production
  final_snapshot_identifier       = format("%s-final", var.name)
  auto_minor_version_upgrade      = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}
resource "aws_secretsmanager_secret" "application" {
  name                    = format("%s/application", var.name)
  kms_key_id              = aws_kms_key.lake.arn
  recovery_window_in_days = 7
}
resource "aws_athena_workgroup" "this" {
  name = var.name
  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 1073741824
    engine_version {
      selected_engine_version = "Athena engine version 3"
    }
    result_configuration {
      output_location = format("s3://%s/athena-results/", aws_s3_bucket.lake.id)
      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = aws_kms_key.lake.arn
      }
    }
  }
}
resource "aws_s3_bucket" "trail" {
  bucket        = format("%s-%s-audit", var.name, data.aws_caller_identity.current.account_id)
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "trail" {
  bucket                  = aws_s3_bucket.trail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "trail" {
  bucket = aws_s3_bucket.trail.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "trail" {
  bucket = aws_s3_bucket.trail.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Effect   = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:GetBucketAcl",
        Resource = aws_s3_bucket.trail.arn,
      Condition = { StringEquals = { "aws:SourceArn" = format("arn:aws:cloudtrail:%s:%s:trail/%s", data.aws_region.current.region, data.aws_caller_identity.current.account_id, var.name) } } },
      { Effect   = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:PutObject",
        Resource = format("%s/AWSLogs/%s/*", aws_s3_bucket.trail.arn, data.aws_caller_identity.current.account_id),
      Condition = { StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control", "aws:SourceArn" = format("arn:aws:cloudtrail:%s:%s:trail/%s", data.aws_region.current.region, data.aws_caller_identity.current.account_id, var.name) } } },
      { Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.trail.arn, format("%s/*", aws_s3_bucket.trail.arn)],
      Condition = { Bool = { "aws:SecureTransport" = "false" } } }
    ]
  })
}
resource "aws_cloudtrail" "this" {
  name                       = var.name
  s3_bucket_name             = aws_s3_bucket.trail.id
  is_multi_region_trail      = true
  enable_log_file_validation = true
  event_selector {
    read_write_type           = "All"
    include_management_events = true
    data_resource {
      type   = "AWS::S3::Object"
      values = [format("%s/", aws_s3_bucket.lake.arn)]
    }
  }
  depends_on = [aws_s3_bucket_policy.trail]
}
output "bucket" {
  value = aws_s3_bucket.lake.id
}
output "bucket_arn" {
  value = aws_s3_bucket.lake.arn
}
output "kms_arn" {
  value = aws_kms_key.lake.arn
}
output "database_host" {
  value = aws_db_instance.source.address
}
output "database_secret_arn" {
  value = aws_db_instance.source.master_user_secret[0].secret_arn
}
output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}
output "workgroup" {
  value = aws_athena_workgroup.this.name
}
output "workgroup_arn" {
  value = aws_athena_workgroup.this.arn
}
