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

# Initialize Sentry for error monitoring
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn and sentry_dsn != "MENTION_KEYS_HERE":
        # Configure Sentry to only capture ERROR level and above
        sentry_logging = LoggingIntegration(
            level=logging.ERROR,        # Capture error and above
            event_level=logging.ERROR   # Send as events only errors and above
        )
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FastApiIntegration(), sentry_logging],
            send_default_pii=True,
            traces_sample_rate=0.1,  # Reduced sample rate for performance
        )
        HAS_SENTRY = True
        print("✅ Sentry initialized successfully (ERROR level only)")
    else:
        HAS_SENTRY = False
        print("⚠️ Sentry DSN not configured - errors will not be tracked")
except ImportError:
    HAS_SENTRY = False
    print("⚠️ Sentry SDK not available - errors will not be tracked")

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

def log_error_to_sentry(error: Exception, context: dict, error_id: str):
    """Log error to Sentry with proper context"""
    if HAS_SENTRY:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("error_id", error_id)
            scope.set_tag("service", "campaign-api")
            scope.set_tag("environment", os.getenv('ENVIRONMENT', 'production'))
            scope.set_context("error_context", context)
            sentry_sdk.capture_exception(error)

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
        # Send to Sentry for ERROR level
        log_error_to_sentry(error, context, error_id)
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
        
        # Determine log level and tag
        if status_code >= 500:
            log_level = "ERROR"
            level_tag = "error"
        elif status_code >= 400:
            log_level = "WARNING"
            level_tag = "warning"
        else:
            log_level = "INFO"
            level_tag = "info"
        
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
            "log_level": level_tag,
            "status_category": level_tag,
            
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
        
        # Log the request with extra fields
        getattr(logger, log_level.lower())(
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

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend HTML page"""
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found</h1><p>Please ensure index.html exists in the project directory.</p>", status_code=404)

@app.get("/api/")
async def api_status():
    """API status endpoint for frontend to check connectivity"""
    return {"message": "Campaign Launch API", "status": "running"}

@app.get("/test/error")
async def test_error():
    """Test endpoint to generate 500 error for logging/Sentry testing"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test/error",
        "operation": "test_error"
    }
    
    test_exception = RuntimeError("This is a test error for logging and Sentry testing")
    
    log_production_error(
        error=test_exception,
        error_type="TestError",
        message="Test error endpoint called",
        context=context,
        error_id=error_id,
        http_status_code=500
    )
    
    raise HTTPException(
        status_code=500,
        detail=create_error_response(
            error_type="TestError",
            message="This is a test error for logging and Sentry testing",
            status_code=500,
            error_id=error_id,
            context=context,
            expose_details=True
        )
    )

@app.post("/campaigns/create")
async def create_campaign(name: str, description: str, db: Session = Depends(get_db)):
    """Step 1: Create a new campaign"""
    try:
        db_campaign = Campaign(
            name=name,
            description=description,
            status="draft"
        )
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        
        logger.info(f"Campaign created: {db_campaign.id}")
        return {
            "id": db_campaign.id,
            "name": db_campaign.name,
            "description": db_campaign.description,
            "status": db_campaign.status,
            "created_at": db_campaign.created_at.isoformat(),
            "is_active": db_campaign.is_active
        }
    except Exception as e:
        db.rollback()
        error_id = generate_error_id()
        context = {
            "campaign_name": name,
            "operation": "create_campaign"
        }
        
        log_production_error(
            error=e,
            error_type="DatabaseError",
            message="Failed to create campaign",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="DatabaseError",
                message="Failed to create campaign due to database error",
                status_code=500,
                error_id=error_id,
                context=context
            )
        )

@app.post("/campaigns/{campaign_id}/validate")
async def validate_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Step 2: Validate campaign before setup"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "Not Found",
                    "message": "Campaign not found",
                    "status_code": 404,
                    "campaign_id": campaign_id,
                    "error_type": "NotFoundError"
                }
            )
        
        validation_errors = []
        
        # Simulate validation logic
        if len(campaign.name) < 3:
            validation_errors.append("Campaign name must be at least 3 characters")
        
        if not campaign.description:
            validation_errors.append("Campaign description is required")
        
        is_valid = len(validation_errors) == 0
        
        if is_valid:
            campaign.status = "validated"
            db.commit()
        
        logger.info(f"Campaign {campaign_id} validation: {'passed' if is_valid else 'failed'}")
        
        return {
            "campaign_id": campaign_id,
            "is_valid": is_valid,
            "validation_errors": validation_errors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Validation Error",
                "message": "Validation service error",
                "status_code": 500,
                "campaign_id": campaign_id,
                "error_type": "ValidationError",
                "details": str(e)
            }
        )

@app.post("/campaigns/{campaign_id}/setup")
async def setup_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Step 3: Setup campaign resources and configuration"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "Not Found",
                    "message": "Campaign not found",
                    "status_code": 404,
                    "campaign_id": campaign_id,
                    "error_type": "NotFoundError"
                }
            )
        
        if campaign.status != "validated":
            raise HTTPException(status_code=400, detail="Campaign must be validated before setup")
        
        # Simulate setup operations
        setup_details = {
            "resources_allocated": True,
            "configuration_applied": True,
            "external_services_connected": True,
            "setup_timestamp": datetime.utcnow().isoformat()
        }
        
        campaign.status = "setup_complete"
        db.commit()
        
        logger.info(f"Campaign {campaign_id} setup completed")
        
        return {
            "campaign_id": campaign_id,
            "setup_complete": True,
            "setup_details": setup_details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail="Setup service error")

@app.post("/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Step 4: Launch campaign - FAILS with database exception"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "Not Found",
                    "message": "Campaign not found",
                    "status_code": 404,
                    "campaign_id": campaign_id,
                    "error_type": "NotFoundError"
                }
            )
        
        if campaign.status != "setup_complete":
            raise HTTPException(status_code=400, detail="Campaign must be setup before launch")
        
        logger.info(f"Attempting to launch campaign {campaign_id}")
        
        # Simulate database exception during launch
        # Force a database error by executing invalid SQL
        db.execute(text("UPDATE non_existent_table SET invalid_column = 'value' WHERE id = :id"), {"id": campaign_id})
        
        # This code should never be reached due to the exception above
        campaign.status = "launched"
        campaign.launched_at = datetime.utcnow()
        campaign.is_active = True
        db.commit()
        
        return {"message": "Campaign launched successfully", "campaign_id": campaign_id}
        
    except OperationalError as e:
        db.rollback()
        logger.error(f"Database operational error during launch of campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Database operational error",
                "message": "Failed to launch campaign due to database exception",
                "campaign_id": campaign_id,
                "error_type": "OperationalError",
                "details": str(e)
            }
        )
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during launch of campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database integrity error", 
                "message": "Campaign launch failed due to data integrity constraints",
                "campaign_id": campaign_id,
                "error_type": "IntegrityError",
                "details": str(e)
            }
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during launch of campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Launch service error",
                "message": "Campaign launch failed due to unexpected error",
                "campaign_id": campaign_id,
                "error_type": type(e).__name__,
                "details": str(e)
            }
        )

@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Get campaign details"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat(),
        "launched_at": campaign.launched_at.isoformat() if campaign.launched_at else None,
        "is_active": campaign.is_active
    }

@app.get("/campaigns/")
async def list_campaigns(db: Session = Depends(get_db)):
    """List all campaigns"""
    campaigns = db.query(Campaign).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
            "launched_at": c.launched_at.isoformat() if c.launched_at else None,
            "is_active": c.is_active
        } for c in campaigns
    ]

@app.post("/campaigns/{campaign_id}/full-launch")
async def full_campaign_launch_flow(campaign_id: int, db: Session = Depends(get_db)):
    """Execute the complete campaign launch flow - will fail at launch step"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "Not Found",
                    "message": "Campaign not found",
                    "status_code": 404,
                    "campaign_id": campaign_id,
                    "error_type": "NotFoundError"
                }
            )
        
        logger.info(f"Starting full launch flow for campaign {campaign_id}")
        
        # Step 1: Validate
        validation_result = await validate_campaign(campaign_id, db)
        if not validation_result["is_valid"]:
            return {
                "status": "failed",
                "step": "validation",
                "errors": validation_result["validation_errors"]
            }
        
        # Step 2: Setup
        setup_result = await setup_campaign(campaign_id, db)
        if not setup_result["setup_complete"]:
            return {
                "status": "failed", 
                "step": "setup",
                "message": "Setup failed"
            }
        
        # Step 3: Launch (will fail)
        await launch_campaign(campaign_id, db)
        
        # This should never be reached
        return {
            "status": "success",
            "message": "Campaign launched successfully",
            "campaign_id": campaign_id
        }
        
    except HTTPException as e:
        return {
            "status": "failed",
            "step": "launch", 
            "error": e.detail,
            "campaign_id": campaign_id
        }
    except Exception as e:
        logger.error(f"Unexpected error in full launch flow for campaign {campaign_id}: {e}")
        return {
            "status": "failed",
            "step": "unknown",
            "error": str(e),
            "campaign_id": campaign_id
        }

@app.get("/test-error")
async def test_error():
    """Test endpoint to trigger Sentry error"""
    logger.error("Test error triggered for Sentry monitoring")
    # Intentionally cause an error
    raise Exception("This is a test error for Sentry - triggered manually")

@app.get("/test-division-error")
async def test_division_error():
    """Test endpoint to trigger division by zero error"""
    logger.error("Division by zero error triggered for Sentry monitoring")
    result = 1 / 0
    return {"result": result}

@app.get("/test-db-connection-error")
async def test_db_connection_error(db: Session = Depends(get_db)):
    """Test endpoint to trigger database connection error"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test-db-connection-error",
        "operation": "test_db_connection"
    }
    
    try:
        # Force a database connection error by executing invalid SQL
        db.execute(text("SELECT * FROM non_existent_table"))
        return {"message": "This should not be reached"}
    except OperationalError as e:
        db.rollback()
        
        log_production_error(
            error=e,
            error_type="DatabaseConnectionError",
            message="Simulated database connection error",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="DatabaseConnectionError",
                message="Database connection failed - this is a test error",
                status_code=500,
                error_id=error_id,
                context=context,
                expose_details=True
            )
        )
    except Exception as e:
        db.rollback()
        
        log_production_error(
            error=e,
            error_type="UnexpectedDatabaseError",
            message="Unexpected database error",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="UnexpectedDatabaseError",
                message="An unexpected database error occurred",
                status_code=500,
                error_id=error_id,
                context=context
            )
        )

@app.get("/test-db-constraint-error")
async def test_db_constraint_error(db: Session = Depends(get_db)):
    """Test endpoint to trigger database constraint/integrity error"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test-db-constraint-error",
        "operation": "test_db_constraint"
    }
    
    try:
        # Try to create a campaign with invalid data to trigger constraint error
        # This will cause an IntegrityError if there are constraints
        db_campaign = Campaign(
            id=1,  # Force duplicate ID if campaign with ID 1 exists
            name="Test Constraint Error",
            description="This should trigger a constraint error",
            status="draft"
        )
        db.add(db_campaign)
        db.commit()
        
        return {"message": "Campaign created (unexpected)"}
        
    except IntegrityError as e:
        db.rollback()
        
        log_production_error(
            error=e,
            error_type="DatabaseConstraintError",
            message="Database constraint violation",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="DatabaseConstraintError",
                message="Database constraint violation - duplicate or invalid data",
                status_code=500,
                error_id=error_id,
                context=context,
                expose_details=True
            )
        )
    except Exception as e:
        db.rollback()
        
        log_production_error(
            error=e,
            error_type="UnexpectedDatabaseError",
            message="Unexpected error during constraint test",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="UnexpectedDatabaseError",
                message="An unexpected error occurred during constraint test",
                status_code=500,
                error_id=error_id,
                context=context
            )
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
