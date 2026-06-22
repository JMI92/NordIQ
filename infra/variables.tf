variable "app_name" {
  description = "Application name used as prefix for all resources"
  type        = string
  default     = "uusio"
}

variable "environment" {
  description = "Deployment environment (production, staging, etc.)"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "api_image" {
  description = "Docker image URI for the API container"
  type        = string
}

variable "frontend_image" {
  description = "Docker image URI for the frontend container"
  type        = string
}

variable "api_cpu" {
  description = "CPU units for the API task (1 vCPU = 1024)"
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Memory (MiB) for the API task"
  type        = number
  default     = 512
}

variable "frontend_cpu" {
  description = "CPU units for the frontend task"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Memory (MiB) for the frontend task"
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

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
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

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "FastAPI secret key for JWT signing"
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "Fernet encryption key for sensitive config fields"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for AI material classification"
  type        = string
  sensitive   = true
  default     = ""
}

variable "smtp_from" {
  description = "From address for SES emails"
  type        = string
  default     = "noreply@uusio.io"
}

variable "domain_name" {
  description = "Primary domain for the application"
  type        = string
  default     = "uusio.io"
}

variable "alert_email" {
  description = "Email address to receive CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "seed_token" {
  description = "One-time token for the /admin/seed endpoint"
  type        = string
  default     = ""
}
