variable "name" {
  type = string
}
variable "private_tasks" {
  type = bool
}
variable "cidr" {
  type = string
}
data "aws_availability_zones" "available" {
  state = "available"
}
resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = format("%s-public-%s", var.name, count.index) }
}
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags              = { Name = format("%s-private-%s", var.name, count.index) }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" {
  count  = var.private_tasks ? 2 : 0
  domain = "vpc"
}
resource "aws_nat_gateway" "this" {
  count         = var.private_tasks ? 2 : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.this]
}
resource "aws_route_table" "private" {
  count  = 2
  vpc_id = aws_vpc.this.id
  dynamic "route" {
    for_each = var.private_tasks ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.this[count.index].id
    }
  }
}
resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = format("com.amazonaws.%s.s3", data.aws_region.current.region)
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)
}
data "aws_region" "current" {}
resource "aws_security_group" "tasks" {
  name_prefix = format("%s-tasks-", var.name)
  vpc_id      = aws_vpc.this.id
  ingress {
    from_port = 8000
    to_port   = 8000
    protocol  = "tcp"
    self      = true
  }
  ingress {
    from_port = 8080
    to_port   = 8080
    protocol  = "tcp"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "database" {
  name_prefix = format("%s-database-", var.name)
  vpc_id      = aws_vpc.this.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.tasks.id]
  }
}
output "vpc_id" {
  value = aws_vpc.this.id
}
output "database_subnets" {
  value = aws_subnet.private[*].id
}
output "task_subnets" {
  value = var.private_tasks ? aws_subnet.private[*].id : aws_subnet.public[*].id
}
output "task_security_group" {
  value = aws_security_group.tasks.id
}
output "database_security_group" {
  value = aws_security_group.database.id
}
output "assign_public_ip" {
  value = !var.private_tasks
}
