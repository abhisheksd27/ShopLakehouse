locals {
  name = format("shoplakehouse-%s", var.environment)
}
module "network" {
  source        = "../modules/network"
  name          = local.name
  cidr          = var.environment == "prod" ? "10.21.0.0/16" : "10.20.0.0/16"
  private_tasks = var.private_tasks
}
module "data" {
  source                  = "../modules/data"
  name                    = local.name
  production              = var.environment == "prod"
  database_subnets        = module.network.database_subnets
  database_security_group = module.network.database_security_group
  db_instance_class       = var.db_instance_class
}
module "compute" {
  source                 = "../modules/compute"
  name                   = local.name
  vpc_id                 = module.network.vpc_id
  subnets                = module.network.task_subnets
  security_group         = module.network.task_security_group
  assign_public_ip       = module.network.assign_public_ip
  bucket                 = module.data.bucket
  bucket_arn             = module.data.bucket_arn
  kms_arn                = module.data.kms_arn
  database_host          = module.data.database_host
  database_secret_arn    = module.data.database_secret_arn
  application_secret_arn = module.data.application_secret_arn
  workgroup              = module.data.workgroup
  workgroup_arn          = module.data.workgroup_arn
  image_tag              = var.image_tag
  deploy_services        = var.deploy_services
  deploy_airflow         = var.deploy_airflow
}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
module "github" {
  source                     = "../modules/github"
  name                       = local.name
  repository                 = var.github_repository
  environment                = var.environment
  existing_oidc_provider_arn = var.existing_oidc_provider_arn
  repositories = [for name in ["app", "airflow"] : format("arn:aws:ecr:%s:%s:repository/%s/%s",
  data.aws_region.current.region, data.aws_caller_identity.current.account_id, local.name, name)]
}
output "cluster" {
  value = module.compute.cluster
}
output "worker_task" {
  value = module.compute.worker_task
}
output "bootstrap_task" {
  value = module.compute.bootstrap_task
}
output "airflow_init_task" {
  value = module.compute.airflow_init_task
}
output "repositories" {
  value = module.compute.repositories
}
output "image_role_arn" {
  value = module.github.image_role_arn
}
output "oidc_provider_arn" {
  value = module.github.oidc_provider_arn
}
output "bucket" {
  value = module.data.bucket
}
output "task_subnets" {
  value = module.network.task_subnets
}
output "task_security_group" {
  value = module.network.task_security_group
}
output "assign_public_ip" {
  value = module.network.assign_public_ip
}
output "application_secret_arn" {
  value = module.data.application_secret_arn
}
