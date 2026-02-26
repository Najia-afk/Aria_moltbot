# Dockerfile for Aria Blue — Multi-stage build
# Stage 1: Builder — install dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source for pip install
COPY pyproject.toml README.md LICENSE ./
COPY aria_mind/ ./aria_mind/
COPY aria_skills/ ./aria_skills/
COPY aria_agents/ ./aria_agents/
COPY aria_models/ ./aria_models/
COPY aria_engine/ ./aria_engine/
COPY scripts/ ./scripts/
COPY src/ ./src/

# Install Python dependencies (non-editable for production)
RUN pip install --no-cache-dir .

# Stage 2: Runtime — lean production image
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (no tests in production)
COPY aria_mind/ ./aria_mind/
COPY aria_skills/ ./aria_skills/
COPY aria_agents/ ./aria_agents/
COPY aria_models/ ./aria_models/
COPY aria_engine/ ./aria_engine/
COPY scripts/ ./scripts/
COPY src/ ./src/

# S-101: Non-root user for security
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria && \
    chown -R aria:aria /app

# Create data directories
RUN mkdir -p /app/data /app/logs && chown -R aria:aria /app/data /app/logs

USER aria

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from aria_mind import AriaMind; print('OK')" || exit 1

# Default command - run startup then stay alive
CMD ["python", "-m", "aria_mind.startup"]
