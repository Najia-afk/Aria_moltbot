FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5000

# Environment
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Run with gunicorn - sync workers are more stable, increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "--keep-alive", "5", "--graceful-timeout", "30", "--max-requests", "1000", "--max-requests-jitter", "50", "app:create_app()"]
