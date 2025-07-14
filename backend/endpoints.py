from fastapi import HTTPException, Depends, Request, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError
from datetime import datetime
import logging
from typing import Optional

try:
    from .database import get_db, Campaign
    from .utils import generate_error_id, create_error_response, log_production_error
except ImportError:
    # For direct execution without package structure
    from database import get_db, Campaign
    from utils import generate_error_id, create_error_response, log_production_error

logger = logging.getLogger(__name__)

router = APIRouter()

# Test error endpoints
@router.get("/test/error")
async def test_error():
    """Test endpoint to generate 500 error for logging testing"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test/error",
        "operation": "test_error"
    }
    
    test_exception = RuntimeError("This is a test error for logging testing")
    
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
            message="This is a test error for logging testing",
            status_code=500,
            error_id=error_id,
            context=context,
            expose_details=True
        )
    )

@router.get("/test-error")
async def test_error_simple():
    """Test endpoint to trigger simple error"""
    logger.error("Test error triggered for monitoring")
    raise Exception("This is a test error - triggered manually")

@router.get("/test-division-error")
async def test_division_error():
    """Test endpoint to trigger division by zero error"""
    logger.error("Division by zero error triggered for monitoring")
    result = 1 / 0
    return {"result": result}

@router.get("/test-db-connection-error")
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

@router.get("/test-table-not-found-error")
async def test_table_not_found_error(db: Session = Depends(get_db)):
    """Test endpoint to trigger table not found database error"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test-table-not-found-error",
        "operation": "test_table_not_found"
    }
    
    try:
        # Attempt to query a non-existent table
        db.execute(text("SELECT * FROM missing_campaigns_table WHERE id = 1"))
        return {"message": "This should not be reached"}
        
    except OperationalError as e:
        db.rollback()
        
        log_production_error(
            error=e,
            error_type="TableNotFoundError",
            message="Attempted to access non-existent database table",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="TableNotFoundError",
                message="Database table 'missing_campaigns_table' does not exist",
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
            message="Unexpected error during table not found test",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="UnexpectedDatabaseError",
                message="An unexpected error occurred during table lookup",
                status_code=500,
                error_id=error_id,
                context=context
            )
        )

@router.get("/test-null-reference-error")
async def test_null_reference_error():
    """Test endpoint to trigger null reference/attribute error"""
    error_id = generate_error_id()
    context = {
        "endpoint": "/test-null-reference-error",
        "operation": "test_null_reference"
    }
    
    try:
        # Create a None object and try to access its attributes
        null_object = None
        
        # This will raise AttributeError: 'NoneType' object has no attribute 'name'
        campaign_name = null_object.name
        
        return {"message": "This should not be reached", "name": campaign_name}
        
    except AttributeError as e:
        log_production_error(
            error=e,
            error_type="NullReferenceError",
            message="Attempted to access attribute on null object",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="NullReferenceError",
                message="Cannot access 'name' attribute on null object - object is None",
                status_code=500,
                error_id=error_id,
                context=context,
                expose_details=True
            )
        )
    except Exception as e:
        log_production_error(
            error=e,
            error_type="UnexpectedError",
            message="Unexpected error during null reference test",
            context=context,
            error_id=error_id,
            http_status_code=500
        )
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_type="UnexpectedError",
                message="An unexpected error occurred during null reference test",
                status_code=500,
                error_id=error_id,
                context=context
            )
        )

@router.get("/test-null-safe-handling")
async def test_null_safe_handling():
    """Demonstrate defensive coding techniques to prevent null reference errors"""
    logger.info("Demonstrating null-safe coding practices")
    
    # Simulate potentially null data (like from database or API)
    campaign_data = None  # This could be a failed database query result
    user_input = None     # This could be missing request data
    config_value = None   # This could be missing configuration
    
    # Method 1: Basic null check with early return
    def safe_get_campaign_name_v1(campaign):
        if campaign is None:
            return "Unknown Campaign"
        return getattr(campaign, 'name', 'Unnamed Campaign')
    
    # Method 2: Using getattr with default value
    def safe_get_campaign_name_v2(campaign):
        return getattr(campaign, 'name', 'Default Campaign') if campaign else 'No Campaign'
    
    # Method 3: Try-except approach
    def safe_get_campaign_name_v3(campaign):
        try:
            return campaign.name
        except AttributeError:
            return "Campaign Name Not Available"
    
    # Method 4: Using Optional type hints and validation
    def safe_process_campaign_data(campaign: Optional[dict]) -> dict:
        if not campaign:
            return {"status": "error", "message": "No campaign data provided"}
        
        # Safely get nested values with defaults
        name = campaign.get('name', 'Untitled Campaign')
        description = campaign.get('description', 'No description available')
        status = campaign.get('status', 'unknown')
        
        return {
            "status": "success",
            "campaign": {
                "name": name,
                "description": description,
                "status": status
            }
        }
    
    # Method 5: Null-safe chain operations
    def safe_get_nested_value(data, *keys, default=None):
        """Safely navigate nested dictionary/object structure"""
        current = data
        for key in keys:
            if current is None:
                return default
            if isinstance(current, dict):
                current = current.get(key)
            else:
                current = getattr(current, key, None)
        return current if current is not None else default
    
    # Demonstrate all approaches
    examples = {
        "method_1_basic_check": safe_get_campaign_name_v1(campaign_data),
        "method_2_getattr": safe_get_campaign_name_v2(campaign_data),
        "method_3_try_except": safe_get_campaign_name_v3(campaign_data),
        "method_4_dict_processing": safe_process_campaign_data(None),
        "method_5_nested_safe": safe_get_nested_value(None, 'campaign', 'metadata', 'name', default="Safe Default")
    }
    
    # Example with actual data to show it works with valid input too
    valid_campaign_dict = {
        "name": "Summer Sale 2025",
        "description": "Our biggest summer campaign",
        "status": "active",
        "metadata": {"created_by": "admin", "priority": "high"}
    }
    
    examples["method_4_with_valid_data"] = safe_process_campaign_data(valid_campaign_dict)
    examples["method_5_with_valid_data"] = safe_get_nested_value(
        valid_campaign_dict, 'metadata', 'created_by', default="Unknown Creator"
    )
    
    return {
        "message": "Null-safe handling examples completed successfully",
        "examples": examples,
        "best_practices": [
            "Always check for None before accessing attributes",
            "Use getattr() with default values",
            "Implement try-except blocks for attribute access",
            "Use Optional type hints for better code clarity",
            "Create utility functions for safe nested access",
            "Return meaningful default values instead of None",
            "Validate input parameters at function entry points"
        ],
        "status": "success"
    }

@router.get("/campaigns/{campaign_id}/analytics")
async def get_campaign_analytics(campaign_id: int, db: Session = Depends(get_db)):
    """
    BROKEN ENDPOINT: This has null pointer vulnerabilities that need fixing via PR
    This endpoint demonstrates real-world null reference errors that could happen
    """
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # PROBLEM 1: Direct attribute access without null checks
        campaign_name = campaign.name.upper()  # Will fail if campaign.name is None
        
        # PROBLEM 2: Unsafe nested attribute access 
        launch_date = campaign.launched_at.strftime("%Y-%m-%d")  # Will fail if launched_at is None
        
        # PROBLEM 3: Unsafe string operations
        description_length = len(campaign.description)  # Will fail if description is None
        
        # PROBLEM 4: Unsafe mathematical operations
        days_active = (datetime.utcnow() - campaign.launched_at).days  # Will fail if launched_at is None
        
        # PROBLEM 5: Unsafe dictionary access from hypothetical external API
        external_data = None  # Simulating failed API call
        conversion_rate = external_data['metrics']['conversion_rate']  # Will fail
        
        return {
            "campaign_id": campaign_id,
            "name": campaign_name,
            "launch_date": launch_date,
            "description_length": description_length,
            "days_active": days_active,
            "conversion_rate": conversion_rate,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Analytics error for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AnalyticsError",
                "message": f"Failed to generate analytics for campaign {campaign_id}",
                "error_details": str(e),
                "campaign_id": campaign_id,
                "fix_needed": "This endpoint needs null-safe defensive coding"
            }
        )

# Campaign management endpoints
@router.post("/campaigns/create")
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

@router.post("/campaigns/{campaign_id}/validate")
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

@router.post("/campaigns/{campaign_id}/setup")
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

@router.post("/campaigns/{campaign_id}/launch")
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

@router.get("/campaigns/{campaign_id}")
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

@router.get("/campaigns/")
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

@router.post("/campaigns/{campaign_id}/full-launch")
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

@router.get("/test-db-constraint-error")
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