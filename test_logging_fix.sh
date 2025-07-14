#!/bin/bash

# Simple test script to verify the logging fix
BASE_URL="http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com"

echo "=== Testing Logging Fix for HTTP 500 Errors ==="
echo ""

# Test the specific endpoint that should trigger a 500 error
echo "Testing /test-table-not-found-error endpoint..."
echo "This should:"
echo "1. Return HTTP 500 status code"
echo "2. Log as ERROR level in DataDog (not INFO)"
echo "3. Include structured error response with error_id, error_type, etc."
echo ""

response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$BASE_URL/test-table-not-found-error")
http_code=$(echo $response | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
body=$(echo $response | sed -E 's/HTTPSTATUS\:[0-9]{3}$//')

echo "HTTP Status Code: $http_code"
echo ""
echo "Response Body:"
echo "$body" | jq . 2>/dev/null || echo "$body"
echo ""

# Verify the response structure
if [ "$http_code" = "500" ]; then
    echo "✓ HTTP Status Code: 500 (correct)"
    
    # Check if response contains expected fields
    if echo "$body" | jq -e '.error_id' > /dev/null 2>&1; then
        echo "✓ Response contains error_id field"
    else
        echo "✗ Response missing error_id field"
    fi
    
    if echo "$body" | jq -e '.error_type' > /dev/null 2>&1; then
        echo "✓ Response contains error_type field"
    else
        echo "✗ Response missing error_type field"
    fi
    
    if echo "$body" | jq -e '.status_code' > /dev/null 2>&1; then
        echo "✓ Response contains status_code field"
    else
        echo "✗ Response missing status_code field"
    fi
    
    if echo "$body" | jq -e '.timestamp' > /dev/null 2>&1; then
        echo "✓ Response contains timestamp field"
    else
        echo "✗ Response missing timestamp field"
    fi
    
else
    echo "✗ HTTP Status Code: $http_code (expected 500)"
fi

echo ""
echo "=== DataDog Verification Steps ==="
echo ""
echo "1. Go to DataDog Logs: https://app.datadoghq.eu/logs"
echo "2. Use this search query: service:campaign-api status:error http.status_code:500"
echo "3. Look for recent log entries with:"
echo "   - level: ERROR (not info)"
echo "   - http.status_code: 500"
echo "   - status_category: error"
echo "   - log_level: error"
echo ""
echo "4. The log message should contain:"
echo "   - Client IP"
echo "   - Request method and path: GET /test-table-not-found-error"
echo "   - Status code: 500"
echo "   - Response time in milliseconds"
echo ""
echo "If you see logs at INFO level instead of ERROR level, the fix hasn't been deployed yet."