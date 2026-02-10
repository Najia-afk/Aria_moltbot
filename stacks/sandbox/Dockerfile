# Aria Sandbox — isolated Python execution environment
FROM python:3.13-alpine

RUN apk add --no-cache git bash curl jq && \
    pip install --no-cache-dir httpx pyyaml structlog pytest

WORKDIR /sandbox

COPY server.py /sandbox/server.py
COPY entrypoint.sh /sandbox/entrypoint.sh
RUN chmod +x /sandbox/entrypoint.sh

EXPOSE 9999

ENTRYPOINT ["/sandbox/entrypoint.sh"]
