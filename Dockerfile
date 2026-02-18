# Dockerfile for Aria Blue
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY aria_mind/ ./aria_mind/
COPY aria_skills/ ./aria_skills/
COPY aria_agents/ ./aria_agents/
COPY aria_models/ ./aria_models/
COPY aria_engine/ ./aria_engine/
COPY tests/ ./tests/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p /app/data /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from aria_mind import AriaMind; print('OK')" || exit 1

# Default command - run startup then stay alive
CMD ["python", "-m", "aria_mind.startup"]
