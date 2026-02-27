# Aria Web Portal — Multi-stage build
# Stage 1: Builder — install dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime — lean production image
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY . .

# S-101: Non-root user for security
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria && \
    chmod +x /app/entrypoint.sh && \
    chown -R aria:aria /app

USER aria

# Expose port
EXPOSE 5000

# Environment
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Run with gunicorn - sync workers are more stable, increased timeout
ENTRYPOINT ["/app/entrypoint.sh"]
