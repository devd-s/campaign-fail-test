import os
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Production error handling utilities
def generate_error_id() -> str:
    """Generate unique error ID for tracking"""
    return str(uuid.uuid4())

def create_error_response(
    error_type: str,
    message: str,
    status_code: int,
    error_id: str,
    context: Optional[dict] = None,
    expose_details: bool = False
) -> dict:
    """Create standardized error response for production"""
    response = {
        "error": error_type,
        "message": message,
        "status_code": status_code,
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Only expose sensitive details in development
    if expose_details and context and os.getenv('ENVIRONMENT') != 'production':
        response["details"] = context
    elif context and "campaign_id" in context:
        # Always safe to expose campaign_id for debugging
        response["campaign_id"] = context["campaign_id"]
    
    return response

# Enhanced logging function
def log_production_error(
    error: Exception,
    error_type: str,
    message: str,
    context: dict,
    error_id: str,
    level: str = "ERROR",
    http_status_code: int = None
):
    """Production-grade error logging"""
    log_data = {
        "error_id": error_id,
        "error_type": error_type,
        "error_message": message,
        "context": context,
        "service": "campaign-api"
    }
    
    # Add HTTP status code to logs
    if http_status_code:
        log_data["http.status_code"] = http_status_code
        log_data["http.status_range"] = f"{http_status_code // 100}xx"
        
        # Determine log level based on HTTP status if not specified
        if level == "ERROR" and http_status_code:
            if 500 <= http_status_code < 600:
                log_data["status_category"] = "error"
            elif 400 <= http_status_code < 500:
                log_data["status_category"] = "warning"
            else:
                log_data["status_category"] = "info"
    
    # Don't log sensitive error details in production logs
    if os.getenv('ENVIRONMENT') != 'production':
        log_data["error_details"] = str(error)
    
    # Create log message with HTTP status
    status_part = f" [HTTP {http_status_code}]" if http_status_code else ""
    log_message = f"[{error_id}]{status_part} {error_type}: {message}"
    
    if level == "ERROR":
        logger.error(log_message, extra=log_data)
    elif level == "WARNING":
        logger.warning(log_message, extra=log_data)
    else:
        logger.info(log_message, extra=log_data)