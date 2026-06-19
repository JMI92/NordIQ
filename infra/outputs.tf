output "alb_dns_name" {
  description = "ALB DNS name — set this as the CNAME target in Cloudflare"
  value       = aws_lb.main.dns_name
}

output "app_url" {
  description = "Public HTTPS URL after Cloudflare DNS is configured"
  value       = "https://${var.domain_name}"
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN"
  value       = aws_acm_certificate.main.arn
}

output "api_ecr_repository_url" {
  description = "ECR URL for the API image"
  value       = aws_ecr_repository.api.repository_url
}

output "frontend_ecr_repository_url" {
  description = "ECR URL for the frontend image"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (private — accessible only from within the VPC)"
  value       = aws_db_instance.main.address
}

output "s3_reports_bucket" {
  description = "S3 bucket name for generated EPR reports"
  value       = aws_s3_bucket.reports.bucket
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "secrets_arn" {
  description = "Secrets Manager ARN — update encryption_key here after first apply"
  value       = aws_secretsmanager_secret.app.arn
}
