# NordIQ — AWS Infrastructure (Terraform)

Deploys NordIQ to AWS using ECS Fargate, RDS PostgreSQL, S3, SES, and ALB.

## Architecture

```
Internet → ALB (public subnets)
              ├─ /api/* → ECS Fargate API    (private subnet, port 8000)
              └─ /*     → ECS Fargate Frontend (private subnet, port 8501)

API → RDS PostgreSQL 15 (private subnet)
API → S3  (EPR report files)
API → SES (deadline warning emails)
API → Secrets Manager (credentials at runtime)
```

## Estimated monthly cost (eu-north-1, minimal setup)

| Resource | Cost/month |
|---|---|
| ECS Fargate (2 tasks × 0.25 vCPU / 512 MB) | ~$15 |
| RDS db.t3.micro PostgreSQL | ~$15 |
| ALB | ~$20 |
| NAT Gateway | ~$35 |
| S3 + CloudWatch | ~$5 |
| **Total** | **~$90/month** |

## Prerequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured (`aws configure`)
- [Terraform >= 1.6](https://developer.hashicorp.com/terraform/install)
- Docker

## First-time deployment

### 1. Authenticate Docker to ECR

```bash
aws ecr get-login-password --region eu-north-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-north-1.amazonaws.com
```

### 2. Build and push images

```bash
# Run from the repo root
docker build -t nordiq-api .

ECR_API=<your-account-id>.dkr.ecr.eu-north-1.amazonaws.com/nordiq-api
ECR_FRONTEND=<your-account-id>.dkr.ecr.eu-north-1.amazonaws.com/nordiq-frontend

docker tag nordiq-api:latest $ECR_API:latest
docker push $ECR_API:latest

# Frontend uses the same image with a different entrypoint
docker tag nordiq-api:latest $ECR_FRONTEND:latest
docker push $ECR_FRONTEND:latest
```

### 3. Configure variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set api_image, frontend_image, smtp_from, alert_email
```

### 4. Deploy

```bash
terraform init
terraform plan   # review what will be created
terraform apply
```

First apply takes ~10 minutes (RDS takes longest).

### 5. Set the Fernet encryption key

After apply, generate a real key and update Secrets Manager:

```bash
# Generate key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Get the secret ARN
terraform output secrets_arn

# Update (replace placeholders)
aws secretsmanager get-secret-value --secret-id <ARN> --query SecretString --output text | \
  python -c "
import sys, json
d = json.load(sys.stdin)
d['encryption_key'] = '<YOUR_FERNET_KEY>'
print(json.dumps(d))
" | xargs -I{} aws secretsmanager put-secret-value --secret-id <ARN> --secret-string '{}'
```

### 6. Run database migrations

```bash
# One-off ECS task using the API image
CLUSTER=$(terraform output -raw ecs_cluster_name)
SUBNET=$(terraform output -json | python -c "import sys,json; print(json.load(sys.stdin)['...'])")

aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition nordiq-api \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<PRIVATE_SUBNET_ID>],securityGroups=[<API_SG_ID>],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

### 7. Access the app

```bash
terraform output alb_dns_name
# Open the URL in your browser
```

## Updating after code changes

```bash
# 1. Build and push a new image
docker build -t nordiq-api . && docker tag nordiq-api:latest $ECR_API:latest && docker push $ECR_API:latest

# 2. Force ECS to deploy the new image
aws ecs update-service --cluster nordiq-production --service nordiq-api --force-new-deployment
```

## Adding HTTPS

1. Request a certificate in [ACM](https://console.aws.amazon.com/acm) for your domain
2. Set `certificate_arn` in `terraform.tfvars`
3. `terraform apply`
4. Add a CNAME record in your DNS pointing to the ALB DNS name

## Destroying the infrastructure

```bash
# Disable RDS deletion protection first
aws rds modify-db-instance \
  --db-instance-identifier nordiq-production \
  --no-deletion-protection \
  --apply-immediately

cd infra && terraform destroy
```
