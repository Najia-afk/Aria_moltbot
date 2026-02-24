# Aria Sandbox — isolated Python execution environment
FROM python:3.13-alpine

RUN apk add --no-cache git bash curl jq && \
    pip install --no-cache-dir httpx pyyaml structlog pytest

WORKDIR /sandbox

COPY server.py /sandbox/server.py
COPY entrypoint.sh /sandbox/entrypoint.sh
RUN chmod +x /sandbox/entrypoint.sh

# S-101: Non-root user for security
RUN addgroup -S -g 1001 aria && \
    adduser -S -u 1001 -G aria aria && \
    chown -R aria:aria /sandbox

USER aria

EXPOSE 9999

ENTRYPOINT ["/sandbox/entrypoint.sh"]
