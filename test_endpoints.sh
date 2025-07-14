#!/bin/bash

# Test script for verifying the logging fix deployment
set -e

BASE_URL="http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com"

echo "=== Testing Campaign API Endpoints ==="
echo "Base URL: $BASE_URL"
echo ""

# Function to test an endpoint
test_endpoint() {
    local endpoint="$1"
    local description="$2"
    local expected_status="$3"
    
    echo "Testing: $description"
    echo "Endpoint: $BASE_URL$endpoint"
    
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nCONTENT_TYPE:%{content_type}\n" "$BASE_URL$endpoint")
    
    # Extract status code
    status_code=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    content_type=$(echo "$response" | grep "CONTENT_TYPE:" | cut -d: -f2)
    body=$(echo "$response" | sed '/HTTP_STATUS:/d' | sed '/CONTENT_TYPE:/d')
    
    echo "Status Code: $status_code"
    echo "Content Type: $content_type"
    echo "Response Body:"
    echo "$body" | jq . 2>/dev/null || echo "$body"
    
    if [ "$status_code" = "$expected_status" ]; then
        echo "✓ Status code matches expected ($expected_status)"
    else
        echo "✗ Status code mismatch. Expected: $expected_status, Got: $status_code"
    fi
    
    echo ""
    echo "---"
    echo ""
}

# Test 1: API Status (should return 200)
test_endpoint "/api/" "API Status Check" "200"

# Test 2: Test Table Not Found Error (should return 500 with structured error)
test_endpoint "/test-table-not-found-error" "Database Table Not Found Error" "500"

# Test 3: Test General Error (should return 500)
test_endpoint "/test/error" "General Test Error" "500"

# Test 4: Test Null Reference Error (should return 500)
test_endpoint "/test-null-reference-error" "Null Reference Error" "500"

echo "=== Test Summary ==="
echo ""
echo "Key points to verify in DataDog logs:"
echo "1. HTTP 500 errors should be logged at ERROR level (not INFO)"
echo "2. Logs should include structured data with:"
echo "   - http.status_code: 500"
echo "   - http.status_range: 5xx"
echo "   - status_category: error"
echo "   - log_level: error"
echo ""
echo "Key points to verify in API responses:"
echo "1. All 500 errors should return structured JSON with:"
echo "   - error_id (UUID)"
echo "   - error_type"
echo "   - message"
echo "   - status_code"
echo "   - timestamp"
echo ""
echo "DataDog Log Search Query:"
echo "service:campaign-api status:error http.status_code:500"