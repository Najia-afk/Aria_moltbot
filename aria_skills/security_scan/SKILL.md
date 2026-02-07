```skill
---
name: aria-securityscan
description: "🔒 Security scanning and vulnerability detection for DevSecOps"
metadata: {"openclaw": {"emoji": "🔒"}}
---
```

# aria-securityscan

Security scanning and vulnerability detection. Scan files/directories for security issues, check dependencies for known CVEs, and audit Dockerfiles.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan <function> '<json_args>'
```

## Functions

### scan_file
Scan a single file for security issues.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan scan_file '{"path": "/root/.openclaw/workspace/app.py"}'
```

### scan_directory
Scan a directory recursively for security issues.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan scan_directory '{"path": "/root/.openclaw/workspace"}'
```

### check_dependencies
Check Python dependencies for known vulnerabilities.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan check_dependencies '{"requirements_path": "/root/.openclaw/workspace/requirements.txt"}'
```

### audit_docker
Audit a Dockerfile for security best practices.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan audit_docker '{"path": "/root/.openclaw/workspace/Dockerfile"}'
```
