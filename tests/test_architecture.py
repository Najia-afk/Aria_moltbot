"""Architecture compliance tests — no running services needed."""
import os
import re
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNoForbiddenImports:
    """Skills must never import SQLAlchemy directly."""

    def test_skills_no_sqlalchemy(self):
        skills_dir = os.path.join(PROJECT_ROOT, "aria_skills")
        if not os.path.isdir(skills_dir):
            pytest.skip("aria_skills not found")
        violations = []
        for root, _, files in os.walk(skills_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if re.search(r"^\s*(from|import)\s+sqlalchemy", content, re.MULTILINE):
                    violations.append(os.path.relpath(path, PROJECT_ROOT))
        assert not violations, f"Skills importing SQLAlchemy: {violations}"

    def test_agents_no_sqlalchemy(self):
        agents_dir = os.path.join(PROJECT_ROOT, "aria_agents")
        if not os.path.isdir(agents_dir):
            pytest.skip("aria_agents not found")
        violations = []
        for root, _, files in os.walk(agents_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if re.search(r"^\s*(from|import)\s+sqlalchemy", content, re.MULTILINE):
                    violations.append(os.path.relpath(path, PROJECT_ROOT))
        assert not violations, f"Agents importing SQLAlchemy: {violations}"


class TestModelsYaml:
    """models.yaml must be the single source of truth."""

    def test_models_yaml_exists(self):
        path = os.path.join(PROJECT_ROOT, "aria_models", "models.yaml")
        assert os.path.isfile(path), "aria_models/models.yaml not found"

    def test_models_yaml_valid(self):
        import yaml
        path = os.path.join(PROJECT_ROOT, "aria_models", "models.yaml")
        if not os.path.isfile(path):
            pytest.skip("models.yaml not found")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, (dict, list)), "models.yaml is not valid YAML"


class TestNoHardcodedSecrets:
    """No API keys or tokens hardcoded in source."""

    PATTERNS = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI-style keys
        r'xoxb-[0-9]{10,}',       # Slack tokens
    ]

    def test_no_secrets_in_source(self):
        source_dirs = ["aria_skills", "aria_engine", "aria_agents", "aria_mind", "src"]
        violations = []
        for d in source_dirs:
            base = os.path.join(PROJECT_ROOT, d)
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    path = os.path.join(root, f)
                    with open(path, encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                    for pat in self.PATTERNS:
                        if re.search(pat, content):
                            violations.append(os.path.relpath(path, PROJECT_ROOT))
                            break
        assert not violations, f"Hardcoded secrets found: {violations}"


class TestCriticalFilesExist:
    """Key files must exist in the repo."""

    REQUIRED = [
        "pyproject.toml",
        "Dockerfile",
        "src/api/main.py",
        "src/api/db/models.py",
        "src/api/deps.py",
        "src/web/app.py",
        "aria_engine/__init__.py",
        "aria_skills/__init__.py",
        "aria_agents/__init__.py",
        "aria_mind/__init__.py",
        "aria_models/models.yaml",
    ]

    @pytest.mark.parametrize("path", REQUIRED)
    def test_file_exists(self, path):
        full = os.path.join(PROJECT_ROOT, path)
        assert os.path.isfile(full), f"Missing critical file: {path}"
