#!/usr/bin/env python3
"""
Test script to verify Datadog log forwarding is working correctly.
This script generates various log levels and types to test the forwarding setup.
"""

import logging
import time
import os
import json
from datetime import datetime

# Try to import Datadog components
try:
    from ddtrace import tracer
    from ddtrace.contrib.logging import patch as logging_patch
    HAS_DATADOG = True
    logging_patch()
except ImportError:
    HAS_DATADOG = False
    print("Datadog not available, testing basic logging only")

# Try to import JSON logger
try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False
    print("JSON logger not available, using standard logging")

def setup_test_logging():
    """Setup logging for testing"""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create appropriate formatter
    if HAS_JSON_LOGGER and os.getenv('ENVIRONMENT') == 'production':
        if HAS_DATADOG:
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s %(dd.trace_id)s %(dd.span_id)s',
                timestamp=True
            )
        else:
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s',
                timestamp=True
            )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def test_log_levels(logger):
    """Test different log levels"""
    logger.debug("DEBUG: This is a debug message for testing")
    logger.info("INFO: Application started successfully")
    logger.warning("WARNING: This is a warning message")
    logger.error("ERROR: This is an error message for testing")
    logger.critical("CRITICAL: This is a critical error message")

def test_structured_logging(logger):
    """Test structured logging with extra fields"""
    logger.info("User login attempt", extra={
        'user_id': 12345,
        'email': 'test@example.com',
        'ip_address': '192.168.1.100',
        'success': True
    })
    
    logger.error("Database connection failed", extra={
        'database': 'campaigns',
        'host': 'localhost',
        'port': 5432,
        'error_code': 'CONNECTION_TIMEOUT'
    })

def test_with_datadog_spans(logger):
    """Test logging with Datadog spans if available"""
    if not HAS_DATADOG:
        logger.info("Datadog not available, skipping span test")
        return
    
    with tracer.trace("test_operation") as span:
        span.set_tag("operation_type", "log_test")
        span.set_tag("test_id", "12345")
        
        logger.info("Inside traced operation - this should include trace ID")
        
        with tracer.trace("nested_operation") as nested_span:
            nested_span.set_tag("nested_level", "1")
            logger.info("Inside nested operation")
            
            # Simulate some work
            time.sleep(0.1)
            
            logger.info("Nested operation completed")
        
        logger.info("Main operation completed")

def main():
    """Main test function"""
    print(f"Starting Datadog logging test at {datetime.now()}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Has Datadog: {HAS_DATADOG}")
    print(f"Has JSON Logger: {HAS_JSON_LOGGER}")
    print("-" * 50)
    
    logger = setup_test_logging()
    
    # Test 1: Basic log levels
    print("Test 1: Testing different log levels...")
    test_log_levels(logger)
    time.sleep(1)
    
    # Test 2: Structured logging
    print("\nTest 2: Testing structured logging...")
    test_structured_logging(logger)
    time.sleep(1)
    
    # Test 3: Datadog spans
    print("\nTest 3: Testing with Datadog spans...")
    test_with_datadog_spans(logger)
    time.sleep(1)
    
    # Test 4: High-frequency logging
    print("\nTest 4: Testing high-frequency logging...")
    for i in range(5):
        logger.info(f"High frequency log message {i+1}/5", extra={
            'iteration': i+1,
            'timestamp': datetime.now().isoformat()
        })
        time.sleep(0.5)
    
    print("\nLogging test completed!")
    print("Check your Datadog dashboard for the forwarded logs.")

if __name__ == "__main__":
    main()