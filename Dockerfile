FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev

COPY requirements-simple.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variable for FastAPI
ENV RUN_ENV=production

# Expose port
EXPOSE 8000

# Use uvicorn to run the FastAPI application
CMD ["uvicorn", "simple_main:app", "--host", "0.0.0.0", "--port", "8000"]
