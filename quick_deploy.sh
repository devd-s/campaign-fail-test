#!/bin/bash

# Quick deployment script for logging fix
set -e

# Configuration
AWS_REGION="eu-central-1"
ECR_REPOSITORY="676190474540.dkr.ecr.eu-central-1.amazonaws.com/campaign-api"
APP_NAME="campaign-api"

echo "=== Campaign API Deployment with Logging Fix ==="
echo "ECR Repository: $ECR_REPOSITORY"
echo "AWS Region: $AWS_REGION"
echo ""

# Step 1: Login to ECR
echo "Step 1: Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin 676190474540.dkr.ecr.eu-central-1.amazonaws.com
echo "✓ ECR login successful"

# Step 2: Build Docker image
echo "Step 2: Building Docker image..."
docker build --platform linux/amd64 -f Dockerfile.production -t $APP_NAME:latest .
echo "✓ Docker image built successfully"

# Step 3: Tag image for ECR
echo "Step 3: Tagging image for ECR..."
docker tag $APP_NAME:latest $ECR_REPOSITORY:latest
echo "✓ Image tagged for ECR"

# Step 4: Push to ECR
echo "Step 4: Pushing image to ECR..."
docker push $ECR_REPOSITORY:latest
echo "✓ Image pushed to ECR successfully"

# Step 5: Update ECS service
echo "Step 5: Updating ECS service..."
aws ecs update-service \
    --cluster campaign-api-cluster \
    --service campaign-api-service \
    --force-new-deployment \
    --region $AWS_REGION
echo "✓ ECS service update initiated"

# Step 6: Wait for deployment
echo "Step 6: Waiting for deployment to complete..."
aws ecs wait services-stable \
    --cluster campaign-api-cluster \
    --services campaign-api-service \
    --region $AWS_REGION
echo "✓ Deployment completed successfully"

echo ""
echo "=== Deployment Summary ==="
echo "✓ Docker image built with logging fix"
echo "✓ Image pushed to ECR"
echo "✓ ECS service updated"
echo "✓ Deployment completed"
echo ""
echo "Load Balancer URL: http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com"
echo "Test endpoint: http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com/test-table-not-found-error"
echo ""
echo "Next steps:"
echo "1. Test the /test-table-not-found-error endpoint"
echo "2. Verify logs in DataDog show ERROR level for 500 status codes"
echo "3. Confirm structured error response includes error_id, error_type, etc."