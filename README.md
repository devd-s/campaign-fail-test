# README.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask web application that provides an item management system with database fallback functionality. The application connects to PostgreSQL by default but automatically falls back to SQLite if PostgreSQL is unavailable.

## Architecture

- **Flask Application** (`app.py`): Main application with database connection logic, model definitions, and routes
- **Database Models**: Single `Item` model with id and name fields
- **Database Strategy**: PostgreSQL-first with SQLite fallback for local development
- **WSGI Entry Point** (`wsgi.py`): Production deployment entry point
- **Containerization** (`Dockerfile`): Docker configuration for deployment

## Key Components

### Database Configuration
The application uses environment variables for database connection:
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` for PostgreSQL
- Automatic fallback to SQLite (`local_cache.db`) when PostgreSQL is unavailable
- Connection testing happens in `get_database_url()` function at app:10-26

### Routes
- `GET/POST /`: Main web interface for item management
- `GET /items`: JSON API endpoint returning all items

## Development Commands

# Virtual Env setup 
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run in development mode
export FLASK_APP=app.py
export FLASK_ENV=development
flask run

# Alternative: Run with Python directly
python app.py
```

### Docker Development
```bash
# Build image
docker build -t item-manager .

# Run in development mode
docker run -e RUN_ENV=development -p 8000:8000 item-manager

# Run in production mode (default)
docker run -p 8000:8000 item-manager
```

### Database Setup
The application automatically creates tables on startup. No manual migration commands are needed.

## Environment Variables

- `RUN_ENV`: Set to "development" for Flask dev server, defaults to production (Gunicorn)
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`: PostgreSQL connection parameters
- `FLASK_APP`: Set to `app.py`
- `FLASK_ENV`: Set to `development` for debug mode

## Dependencies

Core dependencies are managed in `requirements.txt`:
- Flask 2.3.2 with SQLAlchemy extension
- PostgreSQL adapter (psycopg2-binary)
- Gunicorn for production serving

## Commands to launch a campaign 
curl -X POST "http://localhost:8000/campaigns/1/launch"
curl -X GET "http://localhost:8000/campaigns/1"
