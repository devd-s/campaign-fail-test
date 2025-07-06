from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError
from datetime import datetime
from typing import Optional, List
import os
import logging
import sentry_sdk

# Initialize Sentry
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", "MENTION_KEYS_HERE"),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=1.0,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler on when there is an active transaction
    profile_lifecycle="trace",
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Campaign Launch API", version="1.0.0")

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

# Pydantic response models
class CampaignResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: datetime
    launched_at: Optional[datetime] = None
    is_active: bool = False
    
    class Config:
        from_attributes = True

class CampaignValidationResponse(BaseModel):
    campaign_id: int
    is_valid: bool
    validation_errors: List[str]

class CampaignSetupResponse(BaseModel):
    campaign_id: int
    setup_complete: bool
    setup_details: dict

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
    # Serve the HTML interface directly embedded
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Campaign Management System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; }
        .header p { font-size: 1.1rem; opacity: 0.9; }
        .content { padding: 30px; }
        .section { margin-bottom: 40px; }
        .section-title { font-size: 1.8rem; color: #333; margin-bottom: 20px; border-bottom: 3px solid #4facfe; padding-bottom: 10px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #555; }
        input[type="text"], textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: border-color 0.3s; }
        input[type="text"]:focus, textarea:focus { outline: none; border-color: #4facfe; }
        textarea { height: 100px; resize: vertical; }
        .btn { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600; transition: transform 0.2s, box-shadow 0.2s; margin-right: 10px; margin-bottom: 10px; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%); }
        .btn-success { background: linear-gradient(135deg, #51cf66 0%, #40c057 100%); }
        .btn-warning { background: linear-gradient(135deg, #ffd43b 0%, #fab005 100%); color: #333; }
        .campaign-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; margin-top: 20px; }
        .campaign-card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 12px; padding: 20px; transition: transform 0.2s, box-shadow 0.2s; }
        .campaign-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        .campaign-name { font-size: 1.3rem; font-weight: 700; color: #333; margin-bottom: 8px; }
        .campaign-description { color: #666; margin-bottom: 12px; line-height: 1.5; }
        .campaign-status { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 15px; }
        .status-draft { background: #e9ecef; color: #6c757d; }
        .status-validated { background: #d4edda; color: #155724; }
        .status-setup_complete { background: #d1ecf1; color: #0c5460; }
        .status-launched { background: #d4edda; color: #155724; }
        .campaign-meta { font-size: 0.9rem; color: #888; margin-bottom: 15px; }
        .campaign-actions { display: flex; flex-wrap: wrap; gap: 8px; }
        .loading { text-align: center; padding: 20px; color: #666; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; margin: 10px 0; border: 1px solid #f5c6cb; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; margin: 10px 0; border: 1px solid #c3e6cb; }
        .api-status { display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 600; margin-bottom: 20px; }
        .api-online { background: #d4edda; color: #155724; }
        .api-offline { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Campaign Management System</h1>
            <p>Create, manage, and launch marketing campaigns</p>
            <div id="apiStatus" class="api-status">API Status: Online</div>
        </div>

        <div class="content">
            <div class="section">
                <h2 class="section-title">Create New Campaign</h2>
                <form id="campaignForm">
                    <div class="form-group">
                        <label for="campaignName">Campaign Name</label>
                        <input type="text" id="campaignName" placeholder="Enter campaign name" required>
                    </div>
                    <div class="form-group">
                        <label for="campaignDescription">Description</label>
                        <textarea id="campaignDescription" placeholder="Enter campaign description" required></textarea>
                    </div>
                    <button type="submit" class="btn">Create Campaign</button>
                </form>
                <div id="createStatus"></div>
            </div>

            <div class="section">
                <h2 class="section-title">Existing Campaigns</h2>
                <button id="refreshBtn" class="btn">Refresh Campaigns</button>
                <div id="campaignsList">
                    <div class="loading">Loading campaigns...</div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">Test Campaign Flow</h2>
                <div class="form-group">
                    <label for="testCampaignId">Campaign ID for Testing:</label>
                    <input type="number" id="testCampaignId" placeholder="Enter campaign ID" value="1">
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0;">
                    <button class="btn btn-warning" onclick="executeFlowStep('validate')">1. Validate Campaign</button>
                    <button class="btn btn-success" onclick="executeFlowStep('setup')">2. Setup Campaign</button>
                    <button class="btn btn-danger" onclick="executeFlowStep('launch')">3. Launch Campaign (DB Error)</button>
                </div>
                <div id="flowResults"></div>
            </div>

            <div class="section">
                <h2 class="section-title">Database Error Testing</h2>
                <p style="margin-bottom: 15px; color: #666;">Test specific database errors for Datadog monitoring:</p>
                <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0;">
                    <button class="btn btn-danger" onclick="testDatabaseError('table-not-found')">🗄️ Table Not Found Error</button>
                    <button class="btn btn-danger" onclick="testDuplicateError()">🔄 Duplicate ID Error</button>
                </div>
                <div class="form-group" style="max-width: 300px;">
                    <label for="duplicateTestId">ID for Duplicate Test:</label>
                    <input type="number" id="duplicateTestId" placeholder="Enter existing campaign ID" value="1">
                </div>
                <div id="errorTestResults"></div>
            </div>

            <div class="section">
                <h2 class="section-title">Sentry Error Testing</h2>
                <p style="margin-bottom: 15px; color: #666;">Test Sentry error tracking for both frontend and backend:</p>
                <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0;">
                    <button class="btn btn-danger" onclick="testSentryBackendError()">🔧 Backend Error (Division by Zero)</button>
                    <button class="btn btn-danger" onclick="testSentryFrontendError()">💻 Frontend Error (JS Exception)</button>
                    <button class="btn btn-danger" onclick="testSentryFrontendManual()">📝 Manual Frontend Error</button>
                </div>
                <div id="sentryTestResults"></div>
            </div>
        </div>
    </div>

    <script src="https://browser.sentry-cdn.com/7.64.0/bundle.min.js" integrity="sha384-H2cjBeglJJF2OW5Qo45qwPvlWV8wz9m5Dqr7A7XOPZnPb8mBG8VVNUe2P2GbmCQP" crossorigin="anonymous"></script>
    <script>
        // Initialize Sentry for frontend error tracking
        Sentry.init({
            dsn: "MENTION_KEYS_HERE",
            integrations: [
                new Sentry.BrowserTracing(),
            ],
            tracesSampleRate: 1.0,
        });

        const API_BASE = '';
        
        const apiStatus = document.getElementById('apiStatus');
        const campaignForm = document.getElementById('campaignForm');
        const campaignsList = document.getElementById('campaignsList');
        const refreshBtn = document.getElementById('refreshBtn');
        const createStatus = document.getElementById('createStatus');

        campaignForm.addEventListener('submit', createCampaign);
        refreshBtn.addEventListener('click', loadCampaigns);

        loadCampaigns();

        async function createCampaign(event) {
            event.preventDefault();
            
            const name = document.getElementById('campaignName').value;
            const description = document.getElementById('campaignDescription').value;
            
            try {
                const response = await fetch(`${API_BASE}/campaigns/create?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const campaign = await response.json();
                    showSuccess(`Campaign "${campaign.name}" created successfully with ID: ${campaign.id}`);
                    campaignForm.reset();
                    loadCampaigns();
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to create campaign');
                }
            } catch (error) {
                showError(`Error creating campaign: ${error.message}`);
            }
        }

        async function loadCampaigns() {
            campaignsList.innerHTML = '<div class="loading">Loading campaigns...</div>';
            
            try {
                const response = await fetch(`${API_BASE}/campaigns/`);
                if (response.ok) {
                    const campaigns = await response.json();
                    displayCampaigns(campaigns);
                } else {
                    throw new Error('Failed to fetch campaigns');
                }
            } catch (error) {
                campaignsList.innerHTML = `<div class="error">Error loading campaigns: ${error.message}</div>`;
            }
        }

        function displayCampaigns(campaigns) {
            if (campaigns.length === 0) {
                campaignsList.innerHTML = '<div class="loading">No campaigns found. Create your first campaign above!</div>';
                return;
            }

            const campaignsHtml = campaigns.map(campaign => `
                <div class="campaign-card">
                    <div class="campaign-name">${escapeHtml(campaign.name)}</div>
                    <div class="campaign-description">${escapeHtml(campaign.description)}</div>
                    <div class="campaign-status status-${campaign.status}">${campaign.status}</div>
                    <div class="campaign-meta">
                        <div>ID: ${campaign.id}</div>
                        <div>Created: ${new Date(campaign.created_at).toLocaleString()}</div>
                        ${campaign.launched_at ? `<div>Launched: ${new Date(campaign.launched_at).toLocaleString()}</div>` : ''}
                        <div>Active: ${campaign.is_active ? 'Yes' : 'No'}</div>
                    </div>
                    <div class="campaign-actions">
                        ${getCampaignActions(campaign)}
                    </div>
                </div>
            `).join('');

            campaignsList.innerHTML = `<div class="campaign-grid">${campaignsHtml}</div>`;
        }

        function getCampaignActions(campaign) {
            let actions = [];
            
            if (campaign.status === 'draft') {
                actions.push(`<button class="btn btn-warning" onclick="validateCampaign(${campaign.id})">Validate</button>`);
            } else if (campaign.status === 'validated') {
                actions.push(`<button class="btn btn-success" onclick="setupCampaign(${campaign.id})">Setup</button>`);
            } else if (campaign.status === 'setup_complete') {
                actions.push(`<button class="btn btn-danger" onclick="launchCampaign(${campaign.id})">Launch (Will Fail)</button>`);
            }
            
            return actions.join('');
        }

        async function validateCampaign(campaignId) {
            try {
                const response = await fetch(`${API_BASE}/campaigns/${campaignId}/validate`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    if (result.is_valid) {
                        showSuccess(`Campaign ${campaignId} validated successfully!`);
                        loadCampaigns();
                    } else {
                        showError(`Validation failed: ${result.validation_errors.join(', ')}`);
                    }
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Validation failed');
                }
            } catch (error) {
                showError(`Error validating campaign: ${error.message}`);
            }
        }

        async function setupCampaign(campaignId) {
            try {
                const response = await fetch(`${API_BASE}/campaigns/${campaignId}/setup`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showSuccess(`Campaign ${campaignId} setup completed!`);
                    loadCampaigns();
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Setup failed');
                }
            } catch (error) {
                showError(`Error setting up campaign: ${error.message}`);
            }
        }

        async function launchCampaign(campaignId) {
            try {
                const response = await fetch(`${API_BASE}/campaigns/${campaignId}/launch`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    showSuccess(`Campaign ${campaignId} launched successfully!`);
                    loadCampaigns();
                } else {
                    const error = await response.json();
                    showError(`Launch failed as expected: ${error.detail.message || error.detail} (Database Error)`);
                }
            } catch (error) {
                showError(`Error launching campaign: ${error.message}`);
            }
        }

        async function executeFlowStep(step) {
            const campaignId = document.getElementById('testCampaignId').value;
            const resultsDiv = document.getElementById('flowResults');
            
            if (!campaignId) {
                showError('Please enter a valid campaign ID');
                return;
            }

            let url = '';
            let stepName = '';

            switch(step) {
                case 'validate':
                    url = `${API_BASE}/campaigns/${campaignId}/validate`;
                    stepName = 'Validation';
                    break;
                case 'setup':
                    url = `${API_BASE}/campaigns/${campaignId}/setup`;
                    stepName = 'Setup';
                    break;
                case 'launch':
                    url = `${API_BASE}/campaigns/${campaignId}/launch`;
                    stepName = 'Launch';
                    break;
            }

            try {
                const response = await fetch(url, { method: 'POST' });
                const result = await response.json();
                
                const resultDiv = document.createElement('div');
                resultDiv.className = response.ok ? 'success' : 'error';
                resultDiv.innerHTML = `<strong>${stepName} Result:</strong> ${JSON.stringify(result, null, 2)}`;
                
                resultsDiv.insertBefore(resultDiv, resultsDiv.firstChild);
                loadCampaigns();
            } catch (error) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>${stepName} Error:</strong> ${error.message}`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        function showError(message) {
            createStatus.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
            setTimeout(() => createStatus.innerHTML = '', 5000);
        }

        function showSuccess(message) {
            createStatus.innerHTML = `<div class="success">${escapeHtml(message)}</div>`;
            setTimeout(() => createStatus.innerHTML = '', 5000);
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        setInterval(loadCampaigns, 30000);

        // Database error testing functions
        async function testDatabaseError(errorType) {
            const resultsDiv = document.getElementById('errorTestResults');
            let url = '';
            let stepName = '';

            switch(errorType) {
                case 'table-not-found':
                    url = `${API_BASE}/campaigns/test-table-error`;
                    stepName = 'Table Not Found Error';
                    break;
            }

            try {
                const response = await fetch(url, { method: 'POST' });
                const result = await response.json();
                
                const resultDiv = document.createElement('div');
                resultDiv.className = response.ok ? 'success' : 'error';
                resultDiv.innerHTML = `<strong>${stepName} Result:</strong> ${JSON.stringify(result, null, 2)}`;
                
                resultsDiv.insertBefore(resultDiv, resultsDiv.firstChild);
            } catch (error) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>${stepName} Error:</strong> ${error.message}`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        async function testDuplicateError() {
            const campaignId = document.getElementById('duplicateTestId').value;
            const resultsDiv = document.getElementById('errorTestResults');
            
            if (!campaignId) {
                showError('Please enter a valid campaign ID for duplicate test');
                return;
            }

            const url = `${API_BASE}/campaigns/create-duplicate?campaign_id=${campaignId}&name=Duplicate%20Test&description=Testing%20duplicate%20ID%20error`;
            const stepName = 'Duplicate ID Error';

            try {
                const response = await fetch(url, { method: 'POST' });
                const result = await response.json();
                
                const resultDiv = document.createElement('div');
                resultDiv.className = response.ok ? 'success' : 'error';
                resultDiv.innerHTML = `<strong>${stepName} Result:</strong> ${JSON.stringify(result, null, 2)}`;
                
                resultsDiv.insertBefore(resultDiv, resultsDiv.firstChild);
                if (response.ok) {
                    loadCampaigns(); // Refresh if successful
                }
            } catch (error) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>${stepName} Error:</strong> ${error.message}`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        // Sentry error testing functions
        async function testSentryBackendError() {
            const resultsDiv = document.getElementById('sentryTestResults');
            
            try {
                const response = await fetch(`${API_BASE}/sentry-debug`);
                const result = await response.text();
                
                const resultDiv = document.createElement('div');
                resultDiv.className = response.ok ? 'success' : 'error';
                resultDiv.innerHTML = `<strong>Backend Sentry Error Result:</strong> ${result}`;
                
                resultsDiv.insertBefore(resultDiv, resultsDiv.firstChild);
            } catch (error) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>Backend Sentry Error:</strong> ${error.message}`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        function testSentryFrontendError() {
            const resultsDiv = document.getElementById('sentryTestResults');
            
            try {
                // Intentionally cause a frontend JavaScript error
                let undefinedVariable = someUndefinedFunction();
            } catch (error) {
                // Manually capture the error to Sentry
                Sentry.captureException(error);
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>Frontend JS Error Captured:</strong> ${error.message} (Sent to Sentry)`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        function testSentryFrontendManual() {
            const resultsDiv = document.getElementById('sentryTestResults');
            
            // Manually send an error to Sentry
            Sentry.captureMessage("Manual test error from Campaign Management UI", "error");
            
            // Also capture a custom exception
            try {
                throw new Error("Manually triggered frontend error for Sentry testing");
            } catch (error) {
                Sentry.captureException(error);
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<strong>Manual Frontend Error:</strong> ${error.message} (Sent to Sentry)`;
                resultsDiv.insertBefore(errorDiv, resultsDiv.firstChild);
            }
        }

        // Enhanced error handling for all API calls to automatically send to Sentry
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            try {
                const response = await originalFetch.apply(this, args);
                if (!response.ok) {
                    // Capture failed API calls to Sentry
                    Sentry.captureMessage(`API call failed: ${args[0]} - Status: ${response.status}`, "error");
                }
                return response;
            } catch (error) {
                // Capture network errors to Sentry
                Sentry.captureException(error);
                throw error;
            }
        };
    </script>
</body>
</html>'''
    return html_content

@app.get("/api/")
async def api_status():
    return {"message": "Campaign Launch API", "status": "running"}

@app.get("/sentry-debug")
async def trigger_error():
    """Trigger a division by zero error for Sentry testing"""
    division_by_zero = 1 / 0

@app.post("/campaigns/test-table-error")
async def test_table_not_found_error(db: Session = Depends(get_db)):
    """Generate a 'table not found' database error for testing"""
    try:
        # Try to query a non-existent table to generate table not found error
        result = db.execute(text("SELECT * FROM non_existent_campaigns_table WHERE id = 1"))
        return {"message": "This should not be reached"}
    except Exception as e:
        logger.error(f"Database table not found error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database table not found",
                "message": "The campaigns table could not be found in the database",
                "error_type": "TableNotFoundError",
                "sql_error": str(e)
            }
        )

@app.post("/campaigns/create-duplicate")
async def create_campaign_with_duplicate_id(campaign_id: int, name: str, description: str, db: Session = Depends(get_db)):
    """Generate a duplicate key/ID error for testing"""
    try:
        # First, check if campaign with this ID already exists
        existing_campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if existing_campaign:
            logger.error(f"Attempt to create campaign with duplicate ID {campaign_id}. Campaign '{existing_campaign.name}' already exists with this ID.")
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Duplicate campaign ID",
                    "message": f"A campaign with ID {campaign_id} already exists",
                    "existing_campaign": existing_campaign.name,
                    "error_type": "DuplicateKeyError"
                }
            )
        
        # Try to manually insert with specific ID (this might cause integrity constraint issues)
        try:
            # Create campaign with specific ID
            db_campaign = Campaign(
                id=campaign_id,
                name=name,
                description=description,
                status="draft"
            )
            db.add(db_campaign)
            db.commit()
            db.refresh(db_campaign)
            
            logger.info(f"Campaign created with ID: {db_campaign.id}")
            return {
                "id": db_campaign.id,
                "name": db_campaign.name,
                "description": db_campaign.description,
                "status": db_campaign.status,
                "created_at": db_campaign.created_at.isoformat(),
                "launched_at": db_campaign.launched_at.isoformat() if db_campaign.launched_at else None,
                "is_active": db_campaign.is_active
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Database integrity constraint violation - duplicate ID {campaign_id}: {str(e)}")
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Database integrity constraint violation",
                    "message": f"Cannot create campaign: ID {campaign_id} violates unique constraint",
                    "error_type": "IntegrityConstraintError",
                    "sql_error": str(e)
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during duplicate campaign creation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create campaign")

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
            "launched_at": db_campaign.launched_at.isoformat() if db_campaign.launched_at else None,
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
                "error_type": "OperationalError"
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
                "error_type": "IntegrityError"
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
                "error_type": type(e).__name__
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
    return [{
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat(),
        "launched_at": campaign.launched_at.isoformat() if campaign.launched_at else None,
        "is_active": campaign.is_active
    } for campaign in campaigns]

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
        if not validation_result.is_valid:
            return {
                "status": "failed",
                "step": "validation",
                "errors": validation_result.validation_errors
            }
        
        # Step 2: Setup
        setup_result = await setup_campaign(campaign_id, db)
        if not setup_result.setup_complete:
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)