---
name: aria-cicd
description: "🔄 CI/CD pipeline management and automation for DevSecOps"
metadata: {"aria": {"emoji": "🔄"}}
---

# aria-cicd

CI/CD pipeline management. Generate GitHub Actions workflows, validate configs, create Dockerfiles, and analyze deployments.

## Usage

```bash
exec python3 /app/skills/run_skill.py ci_cd <function> '<json_args>'
```

## Functions

### generate_workflow
Generate a GitHub Actions workflow file.

```bash
exec python3 /app/skills/run_skill.py ci_cd generate_workflow '{"name": "deploy", "triggers": ["push"]}'
```

### validate_workflow
Validate a GitHub Actions workflow file.

```bash
exec python3 /app/skills/run_skill.py ci_cd validate_workflow '{"workflow_yaml": "..."}'
```

### generate_dockerfile
Generate a secure Dockerfile.

```bash
exec python3 /app/skills/run_skill.py ci_cd generate_dockerfile '{"base_image": "python:3.12-slim"}'
```

### analyze_deployment
Analyze a docker-compose deployment configuration.

```bash
exec python3 /app/skills/run_skill.py ci_cd analyze_deployment '{"compose_path": "docker-compose.yml"}'
```
