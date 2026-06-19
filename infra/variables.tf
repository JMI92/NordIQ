variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name prefix for all resources"
  type        = string
  default     = "uusio"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (ECS + RDS)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "nordiq"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "nordiq"
}

variable "api_image" {
  description = "Full ECR image URI for the API container"
  type        = string
}

variable "frontend_image" {
  description = "Full ECR image URI for the frontend container"
  type        = string
}

variable "api_cpu" {
  description = "CPU units for the API Fargate task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Memory (MiB) for the API Fargate task"
  type        = number
  default     = 512
}

variable "frontend_cpu" {
  description = "CPU units for the frontend Fargate task"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Memory (MiB) for the frontend Fargate task"
  type        = number
  default     = 512
}

variable "api_desired_count" {
  description = "Number of API task replicas"
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Number of frontend task replicas"
  type        = number
  default     = 1
}

variable "domain_name" {
  description = "Primary domain name (e.g. uusio.io)"
  type        = string
  default     = "uusio.io"
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS. Populated automatically from acm.tf after first apply."
  type        = string
  default     = ""
}

variable "smtp_from" {
  description = "Sender address for SES emails (must be verified in SES)"
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Email address to receive CloudWatch alarm notifications"
  type        = string
  default     = ""
}
