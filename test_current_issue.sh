#!/bin/bash

echo "🔍 Testing Current Error Endpoint Issues"
echo "=============================================="

BASE_URL="http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com"

echo "📋 Issue 1: HTTP 500 should be ERROR level (not INFO)"
echo "📋 Issue 2: Missing structured error response details"
echo ""

echo "🧪 Testing /test-table-not-found-error endpoint..."
echo "URL: ${BASE_URL}/test-table-not-found-error"
echo ""

echo "📊 Response:"
curl -s -w "\nHTTP Status: %{http_code}\n" "${BASE_URL}/test-table-not-found-error" | jq '.' 2>/dev/null || {
    echo "Raw response (non-JSON):"
    curl -s "${BASE_URL}/test-table-not-found-error"
    echo ""
}

echo ""
echo "🔍 Expected after fix:"
echo "  ✅ HTTP Status: 500"
echo "  ✅ Response includes: error_id, error_type, message, status_code, timestamp"
echo "  ✅ DataDog logs show level: ERROR (not info)"

echo ""
echo "📝 To check DataDog logs:"
echo "  1. Go to: https://app.datadoghq.eu/logs"
echo "  2. Search: service:campaign-api path:\"/test-table-not-found-error\""
echo "  3. Check log level is ERROR not INFO"