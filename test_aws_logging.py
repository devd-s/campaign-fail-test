#!/usr/bin/env python3
"""
Test script to verify AWS CloudWatch logging with Datadog forwarding.
This script tests the complete flow: App -> CloudWatch -> Lambda -> Datadog
"""

import logging
import time
import os
import json
from datetime import datetime

# Setup environment for AWS testing
os.environ['ENVIRONMENT'] = 'production'

# Import the logging setup from the main application
try:
    from simple_main import setup_logging
    print("✅ Imported logging setup from main application")
except ImportError as e:
    print(f"❌ Failed to import logging setup: {e}")
    exit(1)

def test_aws_cloudwatch_logging():
    """Test AWS CloudWatch logging integration"""
    print(f"Starting AWS CloudWatch logging test at {datetime.now()}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print("-" * 60)
    
    # Setup logger using the main application's configuration
    logger = setup_logging()
    
    # Test 1: Basic application startup logs
    print("\n🔍 Test 1: Application startup simulation")
    logger.info("Application starting up", extra={
        'component': 'startup',
        'version': '1.0.0',
        'environment': 'production'
    })
    
    logger.info("Database connection established", extra={
        'component': 'database',
        'database_type': 'sqlite',
        'connection_pool_size': 10
    })
    
    logger.info("FastAPI server started", extra={
        'component': 'server',
        'host': '0.0.0.0',
        'port': 8000
    })
    
    time.sleep(2)
    
    # Test 2: Campaign operations (simulating the main application)
    print("\n🔍 Test 2: Campaign operations simulation")
    
    # Simulate campaign creation
    logger.info("Campaign created successfully", extra={
        'operation': 'create_campaign',
        'campaign_id': 12345,
        'campaign_name': 'Test Campaign',
        'user_id': 'user_123',
        'status': 'draft'
    })
    
    # Simulate campaign validation
    logger.info("Campaign validation completed", extra={
        'operation': 'validate_campaign',
        'campaign_id': 12345,
        'validation_result': 'passed',
        'validation_duration_ms': 150
    })
    
    # Simulate campaign setup
    logger.info("Campaign setup completed", extra={
        'operation': 'setup_campaign',
        'campaign_id': 12345,
        'resources_allocated': True,
        'setup_duration_ms': 2500
    })
    
    time.sleep(2)
    
    # Test 3: Error scenarios
    print("\n🔍 Test 3: Error handling simulation")
    
    # Simulate the database error from the main application
    logger.error("Database operational error during campaign launch", extra={
        'operation': 'launch_campaign',
        'campaign_id': 12345,
        'error_type': 'OperationalError',
        'error_message': 'relation "non_existent_table" does not exist',
        'stack_trace': 'sqlalchemy.exc.OperationalError: relation "non_existent_table" does not exist'
    })
    
    # Simulate other types of errors
    logger.warning("High memory usage detected", extra={
        'component': 'monitoring',
        'memory_usage_percent': 85,
        'threshold': 80
    })
    
    logger.error("External API call failed", extra={
        'operation': 'external_api_call',
        'api_endpoint': 'https://api.example.com/v1/data',
        'response_code': 500,
        'retry_count': 3
    })
    
    time.sleep(2)
    
    # Test 4: High-frequency logging
    print("\n🔍 Test 4: High-frequency logging simulation")
    
    for i in range(10):
        logger.info(f"Processing batch item {i+1}/10", extra={
            'operation': 'batch_processing',
            'batch_id': 'batch_001',
            'item_id': f'item_{i+1}',
            'progress': f"{((i+1)/10)*100:.1f}%"
        })
        time.sleep(0.3)
    
    # Test 5: Performance metrics
    print("\n🔍 Test 5: Performance metrics simulation")
    
    logger.info("Request processed", extra={
        'component': 'api',
        'method': 'POST',
        'endpoint': '/campaigns/12345/launch',
        'response_time_ms': 1250,
        'status_code': 500,
        'user_agent': 'Mozilla/5.0 (compatible; TestBot/1.0)'
    })
    
    logger.info("Database query completed", extra={
        'component': 'database',
        'query_type': 'SELECT',
        'table': 'campaigns',
        'execution_time_ms': 45,
        'rows_returned': 1
    })
    
    time.sleep(1)
    
    print("\n✅ AWS CloudWatch logging test completed!")
    print("\nNext steps:")
    print("1. Check AWS CloudWatch Logs console:")
    print("   https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups/log-group/$252Fecs$252Fcampaign-api")
    print("2. Verify Lambda function execution:")
    print("   https://console.aws.amazon.com/lambda/home#/functions/campaign-api-datadog-log-forwarder")
    print("3. Check Datadog logs dashboard:")
    print("   https://app.datadoghq.com/logs")

def main():
    """Main test function"""
    try:
        test_aws_cloudwatch_logging()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
