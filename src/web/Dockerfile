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

# Run with gunicorn - increased timeout for slow DB connections
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--keep-alive", "5", "app:create_app()"]
