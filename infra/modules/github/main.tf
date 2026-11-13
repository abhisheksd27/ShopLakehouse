variable "name" {
  type = string
}
variable "repository" {
  type = string
}
variable "environment" {
  type = string
}
variable "repositories" {
  type = list(string)
}
variable "existing_oidc_provider_arn" {
  type = string
}
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
locals {
  oidc_arn = var.existing_oidc_provider_arn == "" ? aws_iam_openid_connect_provider.github[0].arn : var.existing_oidc_provider_arn
}
resource "aws_iam_role" "images" {
  name = format("%s-github-images", var.name)
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = local.oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = format("repo:%s:environment:%s", var.repository, var.environment)
    } }
  }] })
}
resource "aws_iam_role_policy" "images" {
  role = aws_iam_role.images.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage",
    "ecr:PutImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload"], Resource = var.repositories }
  ] })
}
output "image_role_arn" {
  value = aws_iam_role.images.arn
}
output "oidc_provider_arn" {
  value = local.oidc_arn
}
