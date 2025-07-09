# 🚀 AWS Deployment Guide for Campaign API with Datadog

This guide walks you through deploying the Campaign API to AWS ECS with full Datadog integration for monitoring and logging.

## 📋 Prerequisites

### Required Tools
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [Docker](https://www.docker.com/) installed and running
- [Terraform](https://www.terraform.io/) >= 1.0
- Datadog account with API and Application keys

### Required Accounts & Keys
1. **AWS Account** with appropriate permissions
2. **Datadog Account** - Get your keys from [Datadog API Keys](https://app.datadoghq.com/organization-settings/api-keys)

## 🔧 Quick Setup

### 1. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit with your actual values
export DD_API_KEY="your_datadog_api_key"
export DD_APP_KEY="your_datadog_app_key"
export AWS_REGION="us-east-1"  # Optional, defaults to us-east-1
export APP_NAME="campaign-api"  # Optional, defaults to campaign-api
```

### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region (e.g., us-east-1)
# Enter default output format (json)
```

### 3. Deploy to AWS

```bash
# Make sure you're in the project directory
cd /path/to/your/campaign-api

# Run the deployment script
./deploy.sh
```

## 🏗️ What Gets Deployed

### AWS Infrastructure
- **VPC** with public/private subnets across 2 AZs
- **Application Load Balancer** (ALB) for external access
- **ECS Fargate Cluster** for container orchestration
- **ECR Repository** for Docker images
- **CloudWatch Log Groups** for application logs
- **IAM Roles** with minimal required permissions
- **Security Groups** with restricted access

### Datadog Integration
- **Datadog Agent** as sidecar container
- **Application Performance Monitoring (APM)**
- **Log collection** from all containers
- **Infrastructure monitoring**
- **Custom metrics** from your application

## 📊 Monitoring & Logs in Datadog

### 1. View Your Application
After deployment, check these Datadog sections:

**Infrastructure Monitoring:**
- Go to Infrastructure → Containers
- Filter by `service:campaign-api`

**Application Logs:**
- Go to Logs → Search
- Filter: `service:campaign-api`
- You'll see structured JSON logs from your FastAPI app

**APM (Application Performance Monitoring):**
- Go to APM → Services
- Find `campaign-api` service
- View traces, performance metrics, and errors

### 2. Database Exception Logs
When you trigger the database exception via the API, you'll see in Datadog:

```json
{
  "asctime": "2024-01-01T12:00:00Z",
  "name": "__main__",
  "levelname": "ERROR",
  "message": "Database operational error during launch of campaign 1: (sqlite3.OperationalError) no such table: non_existent_table",
  "service": "campaign-api",
  "env": "production"
}
```

## 🔧 Manual Deployment Steps

If you prefer manual deployment:

### 1. Build and Push Docker Image

```bash
# Get your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"

# Create ECR repository
aws ecr create-repository --repository-name campaign-api --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push
docker build -f Dockerfile.production -t campaign-api:latest .
docker tag campaign-api:latest $ECR_REGISTRY/campaign-api:latest
docker push $ECR_REGISTRY/campaign-api:latest
```

### 2. Deploy Infrastructure

```bash
cd terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan \
  -var="datadog_api_key=$DD_API_KEY" \
  -var="datadog_app_key=$DD_APP_KEY"

# Apply deployment
terraform apply \
  -var="datadog_api_key=$DD_API_KEY" \
  -var="datadog_app_key=$DD_APP_KEY"
```

### 3. Access Your Application

```bash
# Get the load balancer URL
terraform output load_balancer_dns
```

## 🧪 Testing the Deployment

### 1. Check Application Health
```bash
# Replace with your ALB DNS name
curl http://your-alb-dns-name.elb.amazonaws.com/api/
```

### 2. Test Database Exception
```bash
# Create a campaign
curl -X POST "http://your-alb-dns-name.elb.amazonaws.com/campaigns/create?name=Test&description=Test"

# Trigger the database exception (should return 500)
curl -X POST "http://your-alb-dns-name.elb.amazonaws.com/campaigns/1/launch"
```

### 3. Verify Logs in Datadog
- Go to Datadog Logs
- Search for `service:campaign-api level:ERROR`
- You should see the database exception error

## 🏠 Local Development with Datadog

For local testing with Datadog:

```bash
# Set environment variables
export DD_API_KEY="your_datadog_api_key"

# Run with Docker Compose
docker-compose up
```

## 🧹 Cleanup

To destroy all AWS resources:

```bash
cd terraform
terraform destroy \
  -var="datadog_api_key=$DD_API_KEY" \
  -var="datadog_app_key=$DD_APP_KEY"
```

## 💰 Cost Estimation

**Monthly AWS costs (approximate):**
- ALB: ~$16/month
- ECS Fargate (2 tasks): ~$30/month
- CloudWatch Logs: ~$1/month
- ECR storage: ~$1/month
- **Total: ~$48/month**

## 🔒 Security Features

- Non-root container user
- Minimal IAM permissions
- Private subnets for ECS tasks
- Security groups with restricted access
- Secrets stored in AWS Systems Manager Parameter Store

## 🚨 Troubleshooting

### Common Issues

**1. Deployment fails at Docker push:**
```bash
# Ensure AWS credentials are correct
aws sts get-caller-identity

# Ensure Docker is running
docker info
```

**2. ECS tasks fail to start:**
```bash
# Check ECS service events
aws ecs describe-services --cluster campaign-api-cluster --services campaign-api-service
```

**3. No logs in Datadog:**
- Verify DD_API_KEY is correct
- Check Datadog Agent container logs in CloudWatch

### Useful Commands

```bash
# Check ECS service status
aws ecs describe-services --cluster campaign-api-cluster --services campaign-api-service

# View application logs
aws logs tail /ecs/campaign-api --follow

# Force new deployment
aws ecs update-service --cluster campaign-api-cluster --service campaign-api-service --force-new-deployment
```

## 📞 Support

For issues:
1. Check CloudWatch logs in AWS Console
2. Check Datadog logs for application errors
3. Review ECS service events in AWS Console