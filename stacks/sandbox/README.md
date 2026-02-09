# Aria Sandbox

Isolated Python execution environment for safe code experiments.

## Docker Compose Service

Add to `stacks/brain/docker-compose.yml`:

```yaml
  aria-sandbox:
    build: ../../stacks/sandbox
    container_name: aria-sandbox
    restart: unless-stopped
    networks:
      - aria-net
    volumes:
      - ../../aria_skills:/sandbox/aria_skills:ro
      - ../../aria_memories:/sandbox/aria_memories:rw
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
    environment:
      - SANDBOX_PORT=9999
```

## Security

- No internet access (only aria-net internal)
- No port exposure to host
- Resource limits: 2 CPU, 2GB RAM
- Max execution timeout: 120s
- Max code length: 50,000 chars
- Temp files auto-cleaned after execution

## Usage

The sandbox exposes two endpoints:

- `GET /health` — returns `{"status": "healthy"}`
- `POST /exec` — executes Python code
  - Request: `{"code": "print('hello')", "timeout": 30}`
  - Response: `{"stdout": "hello\n", "stderr": "", "exit_code": 0}`

## SandboxSkill

The `aria_skills/sandbox/` skill provides programmatic access from Aria:

```python
result = await sandbox_skill.run_code("print(2 + 2)", timeout=10)
# result.data == {"stdout": "4\n", "stderr": "", "exit_code": 0}
```
