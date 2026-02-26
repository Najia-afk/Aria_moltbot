# Aria API — Multi-stage build
# Stage 1: Builder — install dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime — lean production image
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . ./

# S-101: Non-root user for security
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria && \
    chown -R aria:aria /app

USER aria

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "300"]
