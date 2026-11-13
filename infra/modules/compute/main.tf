variable "name" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "subnets" {
  type = list(string)
}
variable "security_group" {
  type = string
}
variable "assign_public_ip" {
  type = bool
}
variable "bucket" {
  type = string
}
variable "bucket_arn" {
  type = string
}
variable "kms_arn" {
  type = string
}
variable "database_host" {
  type = string
}
variable "database_secret_arn" {
  type = string
}
variable "application_secret_arn" {
  type = string
}
variable "workgroup" {
  type = string
}
variable "workgroup_arn" {
  type = string
}
variable "image_tag" {
  type = string
}
variable "deploy_services" {
  type = bool
}
variable "deploy_airflow" {
  type = bool
}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
resource "aws_ecr_repository" "images" {
  for_each             = toset(["app", "airflow"])
  name                 = format("%s/%s", var.name, each.key)
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_arn
  }
}
resource "aws_ecr_lifecycle_policy" "images" {
  for_each   = aws_ecr_repository.images
  repository = each.value.name
  policy = jsonencode({ rules = [{ rulePriority = 1, description = "Keep last 20 images",
  selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }, action = { type = "expire" } }] })
}
resource "aws_ecs_cluster" "this" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
resource "aws_cloudwatch_log_group" "this" {
  name              = format("/ecs/%s", var.name)
  retention_in_days = 30
}
resource "aws_iam_role" "execution" {
  name = format("%s-execution", var.name)
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
  Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [var.database_secret_arn, var.application_secret_arn] },
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.kms_arn }
  ] })
}
resource "aws_iam_role" "task" {
  name               = format("%s-task", var.name)
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}
resource "aws_iam_role_policy" "task" {
  role = aws_iam_role.task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketLocation"], Resource = var.bucket_arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"], Resource = format("%s/*", var.bucket_arn) },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"], Resource = var.kms_arn },
    { Effect = "Allow", Action = ["glue:GetDatabase", "glue:GetDatabases", "glue:CreateDatabase", "glue:UpdateDatabase",
      "glue:GetTable", "glue:GetTables", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable",
      "glue:GetPartitions", "glue:BatchCreatePartition", "glue:BatchDeletePartition"], Resource = [
      format("arn:aws:glue:%s:%s:catalog", data.aws_region.current.region, data.aws_caller_identity.current.account_id),
      format("arn:aws:glue:%s:%s:database/s_*", data.aws_region.current.region, data.aws_caller_identity.current.account_id),
      format("arn:aws:glue:%s:%s:database/b_*", data.aws_region.current.region, data.aws_caller_identity.current.account_id),
      format("arn:aws:glue:%s:%s:table/s_*/*", data.aws_region.current.region, data.aws_caller_identity.current.account_id),
    format("arn:aws:glue:%s:%s:table/b_*/*", data.aws_region.current.region, data.aws_caller_identity.current.account_id)] },
    { Effect = "Allow", Action = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
    "athena:StopQueryExecution", "athena:GetWorkGroup"], Resource = var.workgroup_arn },
    { Effect = "Allow", Action = ["athena:GetDataCatalog"], Resource = format("arn:aws:athena:%s:%s:datacatalog/AwsDataCatalog",
    data.aws_region.current.region, data.aws_caller_identity.current.account_id) },
    { Effect = "Allow", Action = ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel",
    "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"], Resource = "*" }
  ] })
}
resource "aws_iam_role" "bootstrap" {
  name               = format("%s-bootstrap", var.name)
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}
resource "aws_iam_role_policy" "bootstrap" {
  role = aws_iam_role.bootstrap.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], Resource = var.application_secret_arn },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = var.kms_arn }
  ] })
}
resource "aws_service_discovery_private_dns_namespace" "this" {
  name = format("%s.internal", var.name)
  vpc  = var.vpc_id
}
resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config {

  }
}
locals {
  base_environment = {
    SOURCE_DB_HOST       = var.database_host, SOURCE_DB_PORT = "5432", SOURCE_DB_NAME = "shoplakehouse",
    SOURCE_DB_USER       = "shop_admin", SOURCE_DB_SSLMODE = "require",
    ANALYTICS_DB_HOST    = var.database_host, ANALYTICS_DB_PORT = "5432", ANALYTICS_DB_NAME = "shoplakehouse_analytics",
    ANALYTICS_DB_USER    = "shop_admin", ANALYTICS_DB_SSLMODE = "require",
    AWS_DEFAULT_REGION   = data.aws_region.current.region, LAKE_BUCKET = var.bucket, WAREHOUSE_ENGINE = "athena",
    ATHENA_WORKGROUP     = var.workgroup, APPLICATION_SECRET_ARN = var.application_secret_arn,
    PRODUCT_API_URL      = format("http://api.%s.internal:8000", var.name), SPARK_MASTER = "local[2]",
    GX_ANALYTICS_ENABLED = "false"
  }
  database_secrets = [
    { name = "SOURCE_DB_PASSWORD", valueFrom = format("%s:password::", var.database_secret_arn) },
    { name = "ANALYTICS_DB_PASSWORD", valueFrom = format("%s:password::", var.database_secret_arn) }
  ]
  application_secrets = [
    { name = "PII_HASH_KEY", valueFrom = format("%s:pii_hash_key::", var.application_secret_arn) },
    { name = "API_TOKEN", valueFrom = format("%s:api_token::", var.application_secret_arn) }
  ]
  log_configuration = {
    logDriver = "awslogs", options = {
      awslogs-group = aws_cloudwatch_log_group.this.name,
    awslogs-region = data.aws_region.current.region, awslogs-stream-prefix = "task" }
  }
}
resource "aws_ecs_task_definition" "worker" {
  family                   = format("%s-worker", var.name)
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 8192
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  ephemeral_storage {
    size_in_gib = 30
  }
  container_definitions = jsonencode([{
    name             = "pipeline", image = format("%s:%s", aws_ecr_repository.images["app"].repository_url, var.image_tag),
    essential        = true, command = ["run"],
    environment      = [for key, value in local.base_environment : { name = key, value = value }],
    secrets          = concat(local.database_secrets, local.application_secrets),
    logConfiguration = local.log_configuration
  }])
}
resource "aws_ecs_task_definition" "bootstrap" {
  family                   = format("%s-bootstrap", var.name)
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.bootstrap.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name        = "bootstrap", image = format("%s:%s", aws_ecr_repository.images["app"].repository_url, var.image_tag),
    essential   = true, entryPoint = ["python", "/app/scripts/cloud_bootstrap.py"], command = [],
    environment = [for key, value in local.base_environment : { name = key, value = value }],
    secrets     = local.database_secrets, logConfiguration = local.log_configuration
  }])
}
resource "aws_ecs_task_definition" "api" {
  family                   = format("%s-api", var.name)
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name             = "api", image = format("%s:%s", aws_ecr_repository.images["app"].repository_url, var.image_tag),
    essential        = true, entryPoint = ["uvicorn", "shoplakehouse.api:app", "--host", "0.0.0.0", "--port", "8000"],
    portMappings     = [{ containerPort = 8000, protocol = "tcp" }],
    environment      = [for key, value in local.base_environment : { name = key, value = value }],
    secrets          = concat(local.database_secrets, [local.application_secrets[1]]),
    healthCheck      = { command = ["CMD", "curl", "-f", "http://localhost:8000/health"], interval = 30, timeout = 5, retries = 3, startPeriod = 30 },
    logConfiguration = local.log_configuration
  }])
}
resource "aws_ecs_service" "api" {
  count                  = var.deploy_services ? 1 : 0
  name                   = format("%s-api", var.name)
  cluster                = aws_ecs_cluster.this.id
  task_definition        = aws_ecs_task_definition.api.arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true
  network_configuration {
    subnets          = var.subnets
    security_groups  = [var.security_group]
    assign_public_ip = var.assign_public_ip
  }
  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
resource "aws_ecs_task_definition" "airflow" {
  for_each                 = toset(["scheduler", "webserver", "init"])
  family                   = format("%s-airflow-%s", var.name, each.key)
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 8192
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name         = "airflow", image = format("%s:%s", aws_ecr_repository.images["airflow"].repository_url, var.image_tag),
    essential    = true, entryPoint = ["bash", "/opt/shoplakehouse/scripts/cloud_airflow.sh"], command = [each.key],
    portMappings = each.key == "webserver" ? [{ containerPort = 8080, protocol = "tcp" }] : [],
    environment = [for key, value in merge(local.base_environment, {
      AIRFLOW__CORE__EXECUTOR    = "LocalExecutor", AIRFLOW__CORE__LOAD_EXAMPLES = "false",
      AIRFLOW__CORE__PARALLELISM = "2", AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG = "2",
    DATA_DIR = "/opt/shoplakehouse/data" }) : { name = key, value = value }],
    secrets = concat(local.database_secrets, local.application_secrets, [
      { name = "AIRFLOW__CORE__FERNET_KEY", valueFrom = format("%s:airflow_fernet_key::", var.application_secret_arn) },
      { name = "AIRFLOW__WEBSERVER__SECRET_KEY", valueFrom = format("%s:airflow_webserver_secret_key::", var.application_secret_arn) },
      { name = "AIRFLOW_ADMIN_PASSWORD", valueFrom = format("%s:airflow_admin_password::", var.application_secret_arn) }
    ]),
    logConfiguration = local.log_configuration
  }])
}
resource "aws_ecs_service" "airflow" {
  for_each               = var.deploy_services && var.deploy_airflow ? toset(["scheduler", "webserver"]) : toset([])
  name                   = format("%s-airflow-%s", var.name, each.key)
  cluster                = aws_ecs_cluster.this.id
  task_definition        = aws_ecs_task_definition.airflow[each.key].arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true
  network_configuration {
    subnets          = var.subnets
    security_groups  = [var.security_group]
    assign_public_ip = var.assign_public_ip
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = format("%s-errors", var.name)
  log_group_name = aws_cloudwatch_log_group.this.name
  pattern        = "{ $.level = \"ERROR\" }"
  metric_transformation {
    name      = "PipelineErrors"
    namespace = var.name
    value     = "1"
  }
}
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = format("%s-pipeline-errors", var.name)
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PipelineErrors"
  namespace           = var.name
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
}
resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name
  dashboard_body = jsonencode({ widgets = [{
    type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
      title = "Pipeline errors", region = data.aws_region.current.region, view = "timeSeries",
    metrics = [[var.name, "PipelineErrors"]], period = 300, stat = "Sum" }
  }] })
}
output "cluster" {
  value = aws_ecs_cluster.this.name
}
output "worker_task" {
  value = aws_ecs_task_definition.worker.arn
}
output "bootstrap_task" {
  value = aws_ecs_task_definition.bootstrap.arn
}
output "airflow_init_task" {
  value = aws_ecs_task_definition.airflow["init"].arn
}
output "repositories" {
  value = { for key, value in aws_ecr_repository.images : key => value.repository_url }
}
output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}
output "task_role_arn" {
  value = aws_iam_role.task.arn
}
