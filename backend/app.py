from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exception_handlers import http_exception_handler
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError
from datetime import datetime
import os
import logging
import json
import uuid
from typing import Optional

# Try to import JSON logger for production, fall back to basic logging for development
try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False

# Try to import Datadog tracer
try:
    # Only enable tracing if explicitly enabled
    if os.getenv('DD_TRACE_ENABLED', 'false').lower() == 'true':
        from ddtrace import tracer, patch_all
        from ddtrace.contrib.logging import patch as logging_patch
        HAS_DATADOG = True
        # Auto-instrument common libraries
        patch_all()
        # Patch logging to include trace IDs
        logging_patch()
        print("✅ Datadog tracing enabled")
    else:
        HAS_DATADOG = False
        print("⚠️ Datadog tracing disabled via DD_TRACE_ENABLED=false")
except ImportError:
    HAS_DATADOG = False
    print("⚠️ Datadog tracing not available - ddtrace not installed")

# Try to import AWS CloudWatch logging handler
try:
    import boto3
    from watchtower import CloudWatchLogsHandler
    HAS_CLOUDWATCH = True
except ImportError:
    HAS_CLOUDWATCH = False

# Configure logging for production with JSON format (Datadog-friendly)
def setup_logging():
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove default handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create appropriate formatter
    if HAS_JSON_LOGGER and os.getenv('ENVIRONMENT') == 'production':
        # JSON formatter for production (Datadog)
        if HAS_DATADOG:
            # Include Datadog trace information and HTTP metadata
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s %(dd.trace_id)s %(dd.span_id)s %(http.method)s %(http.url_details.path)s %(http.status_code)s %(http.status_range)s %(network.client.ip)s %(duration)s %(http.useragent)s %(log_level)s %(status_category)s %(service)s %(env)s %(version)s %(dd.service)s %(dd.env)s %(dd.version)s',
                timestamp=True
            )
        else:
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s %(http.method)s %(http.url_details.path)s %(http.status_code)s %(http.status_range)s %(network.client.ip)s %(duration)s %(http.useragent)s %(log_level)s %(status_category)s %(service)s %(env)s %(version)s',
                timestamp=True
            )
    else:
        # Standard formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Add CloudWatch handler in AWS environment
    if HAS_CLOUDWATCH and os.getenv('ENVIRONMENT') == 'production':
        try:
            cloudwatch_handler = CloudWatchLogsHandler(
                log_group='/ecs/campaign-api',
                stream_name=f"campaign-api-{os.getenv('HOSTNAME', 'unknown')}"
            )
            cloudwatch_handler.setFormatter(formatter)
            logger.addHandler(cloudwatch_handler)
        except Exception as e:
            # Fallback if CloudWatch setup fails
            logger.warning(f"Failed to setup CloudWatch logging: {e}")
    
    return logging.getLogger(__name__)

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

# Setup logging
logger = setup_logging()

# Custom logging middleware to capture HTTP status and request metadata
class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Capture request start time
        import time
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate request duration
        process_time = time.time() - start_time
        
        # Extract request metadata
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        status_code = response.status_code
        
        # Determine status code range for Datadog tags
        if 200 <= status_code < 300:
            status_range = "2xx"
        elif 300 <= status_code < 400:
            status_range = "3xx"
        elif 400 <= status_code < 500:
            status_range = "4xx"
        elif 500 <= status_code < 600:
            status_range = "5xx"
        else:
            status_range = "other"
        
        # Log with structured data using Datadog standard attributes
        log_data = {
            # HTTP standard attributes
            "http.method": method.upper(),
            "http.url_details.path": path,
            "http.status_code": status_code,
            "http.status_range": status_range,
            
            # Network attributes
            "network.client.ip": client_ip,
            
            # Performance attributes
            "duration": round(process_time * 1000, 2),  # in milliseconds
            
            # User agent
            "http.useragent": request.headers.get("user-agent", "unknown"),
            
            # Custom tags for filtering
            "log_level": "error" if status_code >= 500 else ("warning" if status_code >= 400 else "info"),
            "status_category": "error" if status_code >= 500 else ("warning" if status_code >= 400 else "info"),
            
            # Service identification
            "service": "campaign-api",
            "env": os.getenv('ENVIRONMENT', 'production'),
            "version": "1.0.0"
        }
        
        # Add Datadog reserved attributes
        if HAS_DATADOG:
            log_data.update({
                "dd.service": "campaign-api",
                "dd.env": os.getenv('ENVIRONMENT', 'production'), 
                "dd.version": "1.0.0"
            })
        
        # Log the request with explicit level based on status code
        if status_code >= 500:
            logger.error(
                f"{client_ip} - \"{method} {path} HTTP/1.1\" {status_code} - {round(process_time * 1000, 2)}ms", 
                extra=log_data
            )
        elif status_code >= 400:
            logger.warning(
                f"{client_ip} - \"{method} {path} HTTP/1.1\" {status_code} - {round(process_time * 1000, 2)}ms", 
                extra=log_data
            )
        else:
            logger.info(
                f"{client_ip} - \"{method} {path} HTTP/1.1\" {status_code} - {round(process_time * 1000, 2)}ms", 
                extra=log_data
            )
        
        return response

app = FastAPI(title="Campaign Launch API", version="1.0.0")

# Custom exception handler for structured error responses
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler that preserves structured error responses"""
    # If the detail is already a dict (structured response), return it as JSON
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Otherwise, use the default handler
    return await http_exception_handler(request, exc)

# Add HTTP logging middleware
app.add_middleware(HTTPLoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./campaigns.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    launched_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}")

# Serve static files for frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend HTML page"""
    try:
        with open("frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found</h1><p>Please ensure frontend/index.html exists.</p>", status_code=404)

@app.get("/api/")
async def api_status():
    """API status endpoint for frontend to check connectivity"""
    return {"message": "Campaign Launch API", "status": "running"}

# Initialize database
try:
    from .database import init_db
    from .endpoints import router
except ImportError:
    # For direct execution without package structure
    from database import init_db
    from endpoints import router

init_db()

# Include all the endpoint routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)