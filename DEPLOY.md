# AWS ECS Deployment Guide

This document contains all the commands and debugging steps used to successfully deploy the Flask Campaign API to AWS ECS with Fargate.

## Prerequisites

Before starting the deployment, ensure you have:
- AWS CLI configured with appropriate credentials
- Docker installed and running
- Terraform installed
- Access to AWS services: ECS, ECR, VPC, ALB, IAM, CloudWatch

## Initial Setup and Configuration

### 1. Check AWS Configuration
```bash
aws configure get region
aws sts get-caller-identity
```

### 2. Verify Project Structure
```bash
ls -la
```

## Docker Image Build and Push

### 3. Create ECR Repository
```bash
aws ecr describe-repositories --region eu-central-1 || echo "ECR access denied"
aws ecr create-repository --repository-name campaign-api --region eu-central-1
```

### 4. Login to ECR
```bash
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 676190474540.dkr.ecr.eu-central-1.amazonaws.com
```

### 5. Build Docker Image (Initial ARM64 Build - FAILED)
```bash
docker build -f Dockerfile.production -t campaign-api:latest .
```

### 6. Fix Architecture Issue - Build for x86_64
```bash
docker build --platform linux/amd64 -f Dockerfile.production -t campaign-api:latest .
```

### 7. Tag and Push Image
```bash
docker tag campaign-api:latest 676190474540.dkr.ecr.eu-central-1.amazonaws.com/campaign-api:latest
docker push 676190474540.dkr.ecr.eu-central-1.amazonaws.com/campaign-api:latest
```

## Infrastructure Deployment with Terraform

### 8. Initialize Terraform
```bash
cd terraform
terraform init
```

### 9. Validate Terraform Configuration
```bash
terraform validate
```

### 10. Plan Infrastructure Deployment
```bash
terraform plan
```

### 11. Apply Infrastructure (Initial Attempt - FAILED)
```bash
terraform apply -auto-approve
```

**Issues Encountered:**
- Load balancer already existed
- ECR repository creation failed due to permissions
- CloudWatch log group creation failed due to insufficient permissions

### 12. Create CloudWatch Log Group Manually
```bash
aws logs create-log-group --log-group-name "/ecs/campaign-api" --region eu-central-1
```

### 13. Check Existing Load Balancer
```bash
aws elbv2 describe-load-balancers --names campaign-api-alb --region eu-central-1
```

### 14. Modified Terraform to Use Existing Resources
Updated `terraform/main.tf` to use data sources instead of creating new resources:
- Changed ECR repository from resource to data source
- Changed Application Load Balancer from resource to data source
- Removed CloudWatch log group resource

### 15. Apply Modified Terraform Configuration
```bash
terraform apply -auto-approve
```

## Application Configuration Fixes

### 16. Fix Application Port Configuration
Updated `simple_main.py` to use port 8000 instead of 7000:
```python
# Changed from:
uvicorn.run(app, host="0.0.0.0", port=7000)
# To:
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 17. Rebuild and Push Updated Image
```bash
docker build --platform linux/amd64 -f Dockerfile.production -t campaign-api:latest .
docker tag campaign-api:latest 676190474540.dkr.ecr.eu-central-1.amazonaws.com/campaign-api:latest
docker push 676190474540.dkr.ecr.eu-central-1.amazonaws.com/campaign-api:latest
```

## ECS Service Management and Debugging

### 18. Update Network Configuration
Modified Terraform to use public subnets instead of private subnets for internet access:
```bash
terraform apply -auto-approve
```

### 19. Force ECS Service Deployment
```bash
aws ecs update-service --cluster campaign-api-cluster --service campaign-api-service --force-new-deployment --region eu-central-1
```

### 20. Monitor ECS Service Status
```bash
aws ecs describe-services --cluster campaign-api-cluster --services campaign-api-service --region eu-central-1 | grep -A 5 -B 5 "runningCount\|status"
```

### 21. Check Task Status
```bash
aws ecs list-tasks --cluster campaign-api-cluster --service-name campaign-api-service --region eu-central-1
```

### 22. Debug Task Failures
```bash
aws ecs describe-tasks --cluster campaign-api-cluster --tasks <task-id> --region eu-central-1
```

### 23. Check Service Running Status
```bash
aws ecs describe-services --cluster campaign-api-cluster --services campaign-api-service --region eu-central-1 --query 'services[0].{RunningCount:runningCount,DesiredCount:desiredCount}' --output table
```

## Application Testing and Verification

### 24. Test Application Health
```bash
curl -s http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/api/
```

### 25. Test Main Page
```bash
curl -s -o /dev/null -w "%{http_code}" http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/
```

### 26. Check Application Response
```bash
curl -s -o /dev/null -w "%{http_code}" http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/api/ && echo " - API status"
```

## Key Issues Resolved

### 1. Architecture Mismatch Error
**Error:** `exec /usr/local/bin/uvicorn: exec format error`
**Solution:** Built Docker image with `--platform linux/amd64` flag

### 2. Port Configuration Mismatch
**Error:** ECS tasks failing to start, 502 Bad Gateway
**Solution:** Changed application port from 7000 to 8000 in `simple_main.py`

### 3. Network Connectivity Issues
**Error:** Tasks in PENDING state, containers failing to start
**Solution:** Changed ECS service to use public subnets with `assign_public_ip = true`

### 4. AWS Permissions Issues
**Error:** CloudWatch log group creation failed, ECR repository creation failed
**Solution:** Created resources manually and used Terraform data sources

### 5. Load Balancer Health Check
**Error:** 503 Service Unavailable
**Solution:** Updated health check path from `/api/` to `/` in target group configuration

## Final Infrastructure

The deployed infrastructure includes:
- **ECS Cluster:** campaign-api-cluster
- **ECS Service:** campaign-api-service (2 tasks)
- **Load Balancer:** campaign-api-alb
- **ECR Repository:** campaign-api
- **Target Group:** campaign-api-tg
- **VPC with subnets:** Public and private subnets across multiple AZs
- **Security Groups:** For ALB and ECS tasks
- **IAM Roles:** ECS execution and task roles

## Application URLs

- **Main Application:** http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/
- **API Health Check:** http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/api/

## DataDog Integration (CONFIGURED)

DataDog log collection is now configured and integrated with the deployment:

### Components Added:
1. **Lambda Log Forwarder**: Official DataDog forwarder function that collects CloudWatch logs
2. **CloudWatch Log Subscription Filter**: Routes ECS logs to DataDog Lambda forwarder
3. **IAM Roles and Policies**: Proper permissions for Lambda execution and log access
4. **Environment Variable**: Deploy script now requires `DD_API_KEY` environment variable

### Deployment with DataDog:
```bash
export DD_API_KEY=your_datadog_api_key_here
./deploy.sh
```

### DataDog Resources Created:
- **Lambda Function**: `campaign-api-datadog-log-forwarder`
- **IAM Role**: `campaign-api-datadog-forwarder-role`
- **Log Subscription Filter**: Routes logs from `/ecs/campaign-api` to DataDog
- **CloudWatch Log Group**: `/ecs/campaign-api` (30-day retention)

### Viewing Logs in DataDog:
- **Location**: DataDog > Logs > Search
- **Service Filter**: `service:campaign-api`
- **Source**: `cloudwatch`
- **Log Format**: JSON structured logs from the application

## Troubleshooting Commands

### Check ECS Task Logs
```bash
aws logs describe-log-streams --log-group-name "/ecs/campaign-api" --region eu-central-1 --order-by LastEventTime --descending --max-items 1
```

### Monitor Service Events
```bash
aws ecs describe-services --cluster campaign-api-cluster --services campaign-api-service --region eu-central-1 --query 'services[0].events[:5]'
```

### Check Target Group Health
```bash
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:eu-central-1:676190474540:targetgroup/campaign-api-tg/09aba3433e8a45c7
```

### List All Tasks (Including Stopped)
```bash
aws ecs list-tasks --cluster campaign-api-cluster --service-name campaign-api-service --region eu-central-1 --desired-status STOPPED
```

## Notes

- All commands assume the AWS region is set to `eu-central-1`
- Replace account ID `676190474540` with your actual AWS account ID
- The deployment uses Fargate launch type for serverless container management
- SQLite database is used with local storage (not recommended for production scaling)
- Health check grace period is set to 0 for faster deployment feedback