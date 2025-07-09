#!/bin/bash

# AWS ECS Deployment Script for Campaign API with Datadog
set -e

# Configuration
AWS_REGION=${AWS_REGION:-"eu-central-1"}
APP_NAME=${APP_NAME:-"campaign-api"}
ECR_REPOSITORY_NAME=${APP_NAME}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check required tools
check_requirements() {
    echo_info "Checking requirements..."
    
    for cmd in aws docker terraform; do
        if ! command -v $cmd &> /dev/null; then
            echo_error "$cmd is required but not installed."
            exit 1
        fi
    done
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo_error "AWS credentials not configured. Run 'aws configure'"
        exit 1
    fi
    
    echo_info "✓ All requirements met"
}

# Build and push Docker image
build_and_push() {
    echo_info "Building and pushing Docker image..."
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}:latest"
    
    # Create ECR repository if it doesn't exist
    aws ecr describe-repositories --repository-names ${ECR_REPOSITORY_NAME} --region ${AWS_REGION} 2>/dev/null || \
    aws ecr create-repository --repository-name ${ECR_REPOSITORY_NAME} --region ${AWS_REGION}
    
    # Login to ECR
    echo_info "Logging into ECR..."
    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
    
    # Build image
    echo_info "Building Docker image..."
    docker build --platform linux/amd64 -f Dockerfile.production -t ${ECR_REPOSITORY_NAME}:latest .
    
    # Tag and push
    echo_info "Pushing to ECR..."
    docker tag ${ECR_REPOSITORY_NAME}:latest ${IMAGE_URI}
    docker push ${IMAGE_URI}
    
    echo_info "✓ Docker image pushed: ${IMAGE_URI}"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    echo_info "Deploying infrastructure with Terraform..."
    
    cd terraform
    
    # Initialize Terraform
    terraform init
    
    # Validate configuration
    terraform validate
    
    # Check for DataDog API key
    if [ -z "$DD_API_KEY" ]; then
        echo_error "DD_API_KEY environment variable is required"
        exit 1
    fi
    
    # Plan deployment
    echo_info "Planning Terraform deployment..."
    terraform plan \
        -var="aws_region=${AWS_REGION}" \
        -var="app_name=${APP_NAME}" \
        -var="datadog_api_key=${DD_API_KEY}"
    
    # Apply deployment
    echo_warn "This will create AWS resources. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        terraform apply \
            -var="aws_region=${AWS_REGION}" \
            -var="app_name=${APP_NAME}" \
            -var="datadog_api_key=${DD_API_KEY}" \
            -auto-approve
    else
        echo_info "Deployment cancelled"
        exit 0
    fi
    
    cd ..
    echo_info "✓ Infrastructure deployed"
}

# Update ECS service
update_service() {
    echo_info "Updating ECS service..."
    
    CLUSTER_NAME="${APP_NAME}-cluster"
    SERVICE_NAME="${APP_NAME}-service"
    
    # Force new deployment
    aws ecs update-service \
        --cluster ${CLUSTER_NAME} \
        --service ${SERVICE_NAME} \
        --force-new-deployment \
        --region ${AWS_REGION}
    
    echo_info "✓ ECS service updated"
    
    # Wait for deployment to complete
    echo_info "Waiting for deployment to complete..."
    aws ecs wait services-stable \
        --cluster ${CLUSTER_NAME} \
        --services ${SERVICE_NAME} \
        --region ${AWS_REGION}
    
    echo_info "✓ Deployment completed successfully"
}

# Get application URL
get_app_url() {
    echo_info "Getting application URL..."
    
    cd terraform
    LOAD_BALANCER_DNS=$(terraform output -raw load_balancer_dns)
    cd ..
    
    echo_info "✓ Application available at: http://${LOAD_BALANCER_DNS}"
    echo_info "  API Status: http://${LOAD_BALANCER_DNS}/api/"
    echo_info "  Frontend: http://${LOAD_BALANCER_DNS}/"
}

# Verify Datadog integration
verify_datadog() {
    echo_info "Verifying Datadog integration..."
    echo_info "Check the following in Datadog:"
    echo_info "  - Infrastructure > Containers"
    echo_info "  - Logs > Search for service:campaign-api"
    echo_info "  - APM > Services > campaign-api"
}

# Main deployment function
main() {
    echo_info "Starting deployment of Campaign API to AWS ECS with Datadog..."
    
    # Environment variables check
    if [ -z "$DD_API_KEY" ]; then
        echo_error "DD_API_KEY environment variable is required for DataDog integration"
        exit 1
    fi
    echo_info "✓ DataDog API key configured"
    
    check_requirements
    build_and_push
    deploy_infrastructure
    update_service
    get_app_url
    verify_datadog
    
    echo_info "🚀 Deployment completed successfully!"
}

# Run deployment
main "$@"