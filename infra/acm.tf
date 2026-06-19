resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}", "api.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${var.app_name}-cert" }
}

# Output the DNS validation records so you can add them to Cloudflare
output "acm_validation_records" {
  description = "Add these CNAME records to Cloudflare to validate the ACM certificate"
  value = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn = aws_acm_certificate.main.arn

  timeouts {
    create = "45m"
  }

  # Run this AFTER adding the CNAME records shown in acm_validation_records output to Cloudflare.
  # Until then, keep this resource commented out and use: terraform apply -target=aws_acm_certificate.main
  lifecycle {
    ignore_changes = [certificate_arn]
  }
}
