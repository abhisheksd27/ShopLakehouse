terraform {
  required_version = ">= 1.10, < 2"
  required_providers {
    aws = {
      source = "hashicorp/aws",
    version = "~> 6.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "ShopLakehouse",
      Environment = "prod",
    ManagedBy = "Terraform" }
  }
}
module "platform" {
  source                     = "../../stack"
  environment                = "prod"
  region                     = var.region
  github_repository          = var.github_repository
  existing_oidc_provider_arn = var.existing_oidc_provider_arn
  image_tag                  = var.image_tag
  deploy_services            = var.deploy_services
  deploy_airflow             = var.deploy_airflow
  db_instance_class          = var.db_instance_class
  private_tasks              = true
}
output "deployment" {
  value = module.platform
}
