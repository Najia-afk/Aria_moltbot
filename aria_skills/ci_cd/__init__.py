# aria_skills/ci_cd.py
"""
🔒 CI/CD Pipeline Skill - DevSecOps Focus

Provides CI/CD pipeline management and automation for Aria's DevSecOps persona.
Integrates with GitHub Actions, Docker, and deployment workflows.
"""
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass 
class PipelineStatus:
    """Status of a CI/CD pipeline."""
    name: str
    status: str  # running, success, failed, pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    url: str | None = None


@SkillRegistry.register
class CICDSkill(BaseSkill):
    """
    CI/CD pipeline management and automation.
    
    Capabilities:
    - GitHub Actions workflow management
    - Docker build orchestration
    - Deployment status tracking
    - Pipeline template generation
    """
    
    @property
    def name(self) -> str:
        return "ci_cd"
    
    async def initialize(self) -> bool:
        """Initialize CI/CD skill."""
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🔄 CI/CD skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check CI/CD availability."""
        return self._status
    
    async def generate_workflow(
        self,
        workflow_type: str,
        language: str = "python",
        options: dict | None = None
    ) -> SkillResult:
        """
        Generate a GitHub Actions workflow file.
        
        Args:
            workflow_type: Type of workflow (test, build, deploy, security)
            language: Programming language (python, node, go)
            options: Additional options (branch, environment, etc.)
            
        Returns:
            SkillResult with generated workflow YAML
        """
        options = options or {}
        
        templates = {
            "test": self._generate_test_workflow,
            "build": self._generate_build_workflow,
            "deploy": self._generate_deploy_workflow,
            "security": self._generate_security_workflow,
        }
        
        if workflow_type not in templates:
            return SkillResult.fail(f"Unknown workflow type: {workflow_type}. Available: {list(templates.keys())}")
        
        try:
            workflow = templates[workflow_type](language, options)
            return SkillResult.ok({
                "workflow_type": workflow_type,
                "language": language,
                "yaml": workflow,
                "filename": f".github/workflows/{workflow_type}.yml"
            })
        except Exception as e:
            return SkillResult.fail(f"Workflow generation failed: {str(e)}")
    
    async def validate_workflow(self, workflow_path: str) -> SkillResult:
        """
        Validate a GitHub Actions workflow file.
        
        Args:
            workflow_path: Path to workflow YAML file
            
        Returns:
            SkillResult with validation results
        """
        try:
            path = Path(workflow_path)
            if not path.exists():
                return SkillResult.fail(f"File not found: {workflow_path}")
            
            content = path.read_text()
            issues = []
            warnings = []
            
            # Check required fields
            if 'name:' not in content:
                warnings.append("Missing 'name' field")
            
            if 'on:' not in content:
                issues.append("Missing 'on' trigger definition")
            
            if 'jobs:' not in content:
                issues.append("Missing 'jobs' definition")
            
            # Security checks
            if 'secrets.' in content and 'secrets.GITHUB_TOKEN' not in content:
                warnings.append("Uses custom secrets - ensure they're configured")
            
            if 'pull_request_target' in content:
                warnings.append("Uses pull_request_target - potential security risk")
            
            if re.search(r'\$\{\{.*github\.event\..*\}\}', content):
                warnings.append("Uses event context - validate input handling")
            
            # Best practices
            if 'timeout-minutes' not in content:
                warnings.append("No timeout-minutes set - jobs may run indefinitely")
            
            if 'concurrency:' not in content:
                warnings.append("No concurrency control - parallel runs may conflict")
            
            return SkillResult.ok({
                "file": str(path),
                "valid": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
                "validated_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Validation failed: {str(e)}")
    
    async def generate_dockerfile(
        self,
        language: str = "python",
        base_image: str | None = None,
        options: dict | None = None
    ) -> SkillResult:
        """
        Generate a secure Dockerfile.
        
        Args:
            language: Programming language
            base_image: Custom base image
            options: Additional options (port, entrypoint, etc.)
            
        Returns:
            SkillResult with generated Dockerfile
        """
        options = options or {}
        
        templates = {
            "python": self._generate_python_dockerfile,
            "node": self._generate_node_dockerfile,
        }
        
        if language not in templates:
            return SkillResult.fail(f"Unsupported language: {language}")
        
        try:
            dockerfile = templates[language](base_image, options)
            return SkillResult.ok({
                "language": language,
                "dockerfile": dockerfile,
                "filename": "Dockerfile"
            })
        except Exception as e:
            return SkillResult.fail(f"Dockerfile generation failed: {str(e)}")
    
    async def analyze_deployment(self, compose_file: str) -> SkillResult:
        """
        Analyze a docker-compose deployment configuration.
        
        Args:
            compose_file: Path to docker-compose.yml
            
        Returns:
            SkillResult with deployment analysis
        """
        try:
            path = Path(compose_file)
            if not path.exists():
                return SkillResult.fail(f"File not found: {compose_file}")
            
            content = path.read_text()
            
            # Parse services
            services = []
            current_service = None
            indent_level = 0
            
            for line in content.split('\n'):
                stripped = line.strip()
                if line.startswith('  ') and not line.startswith('    ') and ':' in stripped:
                    # Service definition
                    service_name = stripped.rstrip(':')
                    if not service_name.startswith('#'):
                        current_service = {"name": service_name, "ports": [], "depends_on": [], "volumes": []}
                        services.append(current_service)
                elif current_service:
                    if 'ports:' in stripped:
                        indent_level = 1
                    elif 'depends_on:' in stripped:
                        indent_level = 2
                    elif 'volumes:' in stripped:
                        indent_level = 3
                    elif stripped.startswith('- '):
                        value = stripped[2:].strip('"\'')
                        if indent_level == 1:
                            current_service["ports"].append(value)
                        elif indent_level == 2:
                            current_service["depends_on"].append(value)
                        elif indent_level == 3:
                            current_service["volumes"].append(value)
            
            # Security analysis
            warnings = []
            for svc in services:
                # Check for privileged ports
                for port in svc.get("ports", []):
                    if ':' in port:
                        host_port = port.split(':')[0]
                        if host_port.isdigit() and int(host_port) < 1024:
                            warnings.append(f"{svc['name']}: Uses privileged port {host_port}")
                
                # Check for host volumes
                for vol in svc.get("volumes", []):
                    if vol.startswith('/') and ':' in vol:
                        warnings.append(f"{svc['name']}: Mounts host path {vol.split(':')[0]}")
            
            return SkillResult.ok({
                "file": str(path),
                "services": services,
                "service_count": len(services),
                "warnings": warnings,
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Analysis failed: {str(e)}")
    
    # === Private Template Methods ===
    
    def _generate_test_workflow(self, language: str, options: dict) -> str:
        """Generate a test workflow."""
        branch = options.get("branch", "main")
        
        if language == "python":
            return f'''name: Tests

on:
  push:
    branches: [ {branch} ]
  pull_request:
    branches: [ {branch} ]

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[test]"
    
    - name: Run tests
      run: |
        pytest tests/ -v --tb=short
'''
        return "# Unsupported language"
    
    def _generate_build_workflow(self, language: str, options: dict) -> str:
        """Generate a build workflow."""
        registry = options.get("registry", "ghcr.io")
        
        return f'''name: Build

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      packages: write
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Registry
      uses: docker/login-action@v3
      with:
        registry: {registry}
        username: ${{{{ github.actor }}}}
        password: ${{{{ secrets.GITHUB_TOKEN }}}}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: {registry}/${{{{ github.repository }}}}:${{{{ github.sha }}}}
        cache-from: type=gha
        cache-to: type=gha,mode=max
'''
    
    def _generate_deploy_workflow(self, language: str, options: dict) -> str:
        """Generate a deploy workflow."""
        env = options.get("environment", "production")
        
        return f'''name: Deploy

on:
  workflow_dispatch:
  push:
    tags: [ 'v*' ]

concurrency:
  group: deploy-{env}
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: {env}
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy
      run: |
        echo "Deploying to {env}..."
        # Add deployment commands here
    
    - name: Health check
      run: |
        sleep 10
        curl -f ${{{{ vars.HEALTH_URL }}}} || exit 1
'''
    
    def _generate_security_workflow(self, language: str, options: dict) -> str:
        """Generate a security scanning workflow."""
        return '''name: Security Scan

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  security:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      security-events: write
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: 'trivy-results.sarif'
'''
    
    def _generate_python_dockerfile(self, base_image: str | None, options: dict) -> str:
        """Generate a secure Python Dockerfile."""
        base = base_image or "python:3.11-slim"
        port = options.get("port", 8000)
        
        return f'''# Multi-stage build for smaller, more secure images
FROM {base} AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM {base}

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/app/.local

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# Add .local/bin to PATH
ENV PATH=/home/app/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{port}/health || exit 1

EXPOSE {port}

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]
'''
    
    def _generate_node_dockerfile(self, base_image: str | None, options: dict) -> str:
        """Generate a secure Node.js Dockerfile."""
        base = base_image or "node:20-slim"
        port = options.get("port", 3000)
        
        return f'''FROM {base} AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

FROM {base}

WORKDIR /app

RUN useradd --create-home --shell /bin/bash app

COPY --from=builder /app/node_modules ./node_modules
COPY --chown=app:app . .

USER app

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{port}/health || exit 1

EXPOSE {port}

CMD ["node", "index.js"]
'''
