#!/bin/bash

# Deploy Datadog Log Forwarder to AWS
# Usage: ./deploy_log_forwarder.sh

set -e

echo "Deploying Datadog Log Forwarder to AWS..."
echo "========================================="

# Check if required environment variables are set
if [ -z "$DD_API_KEY" ]; then
    echo "Error: DD_API_KEY environment variable is not set"
    echo "Please set your Datadog API key:"
    echo "export DD_API_KEY=your_api_key_here"
    exit 1
fi

if [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "Error: AWS credentials not set"
    echo "Please configure AWS credentials:"
    echo "export AWS_ACCESS_KEY_ID=your_access_key"
    echo "export AWS_SECRET_ACCESS_KEY=your_secret_key"
    exit 1
fi

echo "✓ Environment variables are set"

# Check if terraform is available
if ! command -v terraform &> /dev/null; then
    echo "Error: terraform is not installed"
    echo "Please install terraform: https://learn.hashicorp.com/tutorials/terraform/install-cli"
    exit 1
fi

echo "✓ Terraform is available"

# Navigate to terraform directory
cd terraform

# Initialize Terraform
echo ""
echo "Initializing Terraform..."
terraform init

# Plan the deployment
echo ""
echo "Planning Terraform deployment..."
terraform plan -var="datadog_api_key=$DD_API_KEY" -out=tfplan

# Ask for confirmation
echo ""
read -p "Do you want to apply these changes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Applying Terraform changes..."
    terraform apply tfplan
    
    echo ""
    echo "✅ Datadog log forwarder deployed successfully!"
    echo ""
    echo "Log forwarder details:"
    terraform output datadog_forwarder_arn
    
    echo ""
    echo "Your logs will now be forwarded from CloudWatch to Datadog."
    echo "Check your Datadog dashboard: https://app.datadoghq.com/logs"
    
else
    echo "Deployment cancelled."
    rm -f tfplan
fi

cd ..