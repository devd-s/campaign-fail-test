#!/bin/bash

# Script to start the application with Datadog log forwarding
# Usage: ./start_with_logs.sh

set -e

echo "Starting Datadog Log Forwarding Test..."
echo "======================================"

# Check if DD_API_KEY is set
if [ -z "$DD_API_KEY" ]; then
    echo "Error: DD_API_KEY environment variable is not set"
    echo "Please set your Datadog API key:"
    echo "export DD_API_KEY=your_api_key_here"
    exit 1
fi

echo "✓ DD_API_KEY is set"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

echo "✓ docker-compose is available"

# Build and start services
echo ""
echo "Building and starting services..."
echo "This may take a few minutes on first run..."

# Stop any existing containers
docker-compose down 2>/dev/null || true

# Build and start
docker-compose up --build -d

# Wait for services to be ready
echo ""
echo "Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✓ Services are running"
else
    echo "❌ Services failed to start"
    docker-compose logs
    exit 1
fi

# Run logging test inside the container
echo ""
echo "Running logging test..."
docker-compose exec campaign-api python test_logging.py

echo ""
echo "Log forwarding test completed!"
echo ""
echo "To view logs:"
echo "1. Check Datadog dashboard: https://app.datadoghq.com/logs"
echo "2. View container logs: docker-compose logs -f campaign-api"
echo "3. View all logs: docker-compose logs -f"
echo ""
echo "To stop services: docker-compose down"