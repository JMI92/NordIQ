terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment to store state in S3 (recommended for teams)
  # backend "s3" {
  #   bucket  = "your-terraform-state-bucket"
  #   key     = "nordiq/terraform.tfstate"
  #   region  = "eu-north-1"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "NordIQ"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}
