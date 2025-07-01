FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variable for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Use an environment variable to determine whether to run with Flask or Gunicorn
ENV RUN_ENV=production

# Use a shell form CMD to allow for environment variable substitution
CMD if [ "$RUN_ENV" = "development" ] ; then flask run --port=8000 ; else gunicorn --bind 0.0.0.0:8000 wsgi:app ; fi
