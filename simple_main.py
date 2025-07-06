from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError
from datetime import datetime
import os
import logging
import json

# Initialize Sentry for error monitoring
try:
    import sentry_sdk
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", "MENTION_KEYS_HERE"),
        send_default_pii=True,
        traces_sample_rate=1.0,
    )
    HAS_SENTRY = True
    print("✅ Sentry initialized successfully")
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
    from ddtrace import tracer, patch_all
    from ddtrace.contrib.logging import patch as logging_patch
    HAS_DATADOG = True
    # Auto-instrument common libraries
    patch_all()
    # Patch logging to include trace IDs
    logging_patch()
except ImportError:
    HAS_DATADOG = False

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
            # Include Datadog trace information
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

# Setup logging
logger = setup_logging()

app = FastAPI(title="Campaign Launch API", version="1.0.0")

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
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail="Failed to create campaign")

@app.post("/campaigns/{campaign_id}/validate")
async def validate_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Step 2: Validate campaign before setup"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
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
        raise HTTPException(status_code=500, detail="Validation service error")

@app.post("/campaigns/{campaign_id}/setup")
async def setup_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Step 3: Setup campaign resources and configuration"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
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
            raise HTTPException(status_code=404, detail="Campaign not found")
        
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
            raise HTTPException(status_code=404, detail="Campaign not found")
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
