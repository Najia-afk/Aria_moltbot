# Aria Sandbox — isolated Python execution environment
FROM python:3.12-alpine

RUN apk add --no-cache git bash curl jq && \
    pip install --no-cache-dir httpx pyyaml structlog pytest

WORKDIR /sandbox

COPY entrypoint.py /sandbox/entrypoint.py

EXPOSE 9999

CMD ["python", "/sandbox/entrypoint.py"]
