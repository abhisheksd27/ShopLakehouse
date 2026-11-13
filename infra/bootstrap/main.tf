terraform {
  required_version = ">= 1.10, < 2"
  required_providers {
    aws = {
      source = "hashicorp/aws",
    version = "~> 6.0" }
  }
}
variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "state_bucket" {
  type = string
}
provider "aws" {
  region = var.region
}
resource "aws_kms_key" "state" {
  description             = "ShopLakehouse Terraform state"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
    bucket_key_enabled = true
  }
}
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [aws_s3_bucket.state.arn, format("%s/*", aws_s3_bucket.state.arn)],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
output "bucket" {
  value = aws_s3_bucket.state.id
}
output "kms_key_arn" {
  value = aws_kms_key.state.arn
}
