variable "environment" {
  type = string
}
variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "github_repository" {
  type    = string
  default = "abhisheksd27/ShopLakehouse"
}
variable "existing_oidc_provider_arn" {
  type    = string
  default = ""
}
variable "image_tag" {
  type    = string
  default = "bootstrap"
}
variable "deploy_services" {
  type    = bool
  default = false
}
variable "deploy_airflow" {
  type    = bool
  default = false
}
variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "private_tasks" {
  type    = bool
  default = false
}
