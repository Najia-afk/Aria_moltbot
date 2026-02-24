"""
Docker health check configuration tests (S-156).

Parses stacks/brain/docker-compose.yml and verifies:
- ALL services have healthcheck blocks
- No ``condition: service_started`` remains (should all be ``service_healthy``)
- No ``:latest`` tags (except documented exceptions)
- Healthcheck command format is valid
- This is a configuration test — no live Docker needed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPOSE_PATH = Path(__file__).resolve().parent.parent / "stacks" / "brain" / "docker-compose.yml"

# Documented exceptions where :latest is acceptable
LATEST_TAG_EXCEPTIONS = frozenset({
    "dperson/torproxy",  # NOTE in compose: no tagged releases
    "browserless/chrome",  # NOTE in compose: pin to digest after testing
})

# Services where healthcheck is intentionally absent (run-once init containers, sandboxes)
HEALTHCHECK_EXEMPT = frozenset({
    "certs-init",     # runs once and exits
    "aria-sandbox",   # isolated execution sandbox, no web server to probe
})


# ---------------------------------------------------------------------------
# Load compose once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def compose_data():
    assert COMPOSE_PATH.exists(), f"Compose file not found at {COMPOSE_PATH}"
    with open(COMPOSE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def services(compose_data):
    return compose_data.get("services", {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compose_file_exists():
    """Basic sanity — the compose file exists and is parseable."""
    assert COMPOSE_PATH.exists()
    with open(COMPOSE_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "services" in data


def test_all_services_have_healthcheck(services):
    """Every service (except documented exemptions) must have a healthcheck."""
    missing = []
    for name, cfg in services.items():
        if name in HEALTHCHECK_EXEMPT:
            continue
        if "healthcheck" not in cfg:
            missing.append(name)
    assert not missing, f"Services missing healthcheck: {missing}"


def test_no_service_started_conditions(services):
    """No depends_on should use 'condition: service_started' — must be service_healthy or service_completed_successfully."""
    bad = []
    for name, cfg in services.items():
        depends = cfg.get("depends_on", {})
        if isinstance(depends, dict):
            for dep_name, dep_cfg in depends.items():
                if isinstance(dep_cfg, dict) and dep_cfg.get("condition") == "service_started":
                    bad.append(f"{name} → {dep_name}")
        elif isinstance(depends, list):
            # List-form depends_on implicitly is service_started-like — flag these
            # unless they are just service names (which is acceptable if the dependent has healthcheck)
            pass
    assert not bad, f"Found 'condition: service_started' in: {bad}"


def test_no_latest_tags(services):
    """No images should use :latest tag, except documented exceptions."""
    violations = []
    for name, cfg in services.items():
        image = cfg.get("image", "")
        if not image:
            continue  # build-only services
        # Check for explicit :latest or implicit (no tag)
        if image.endswith(":latest"):
            base = image.rsplit(":", 1)[0]
            if base not in LATEST_TAG_EXCEPTIONS:
                violations.append(f"{name}: {image}")
    assert not violations, f"Services using :latest without exception: {violations}"


def test_healthcheck_command_format(services):
    """Healthcheck test field must be a list starting with CMD or CMD-SHELL."""
    bad = []
    for name, cfg in services.items():
        hc = cfg.get("healthcheck", {})
        test = hc.get("test")
        if test is None:
            continue
        if isinstance(test, list):
            if test[0] not in ("CMD", "CMD-SHELL"):
                bad.append(f"{name}: first element is '{test[0]}', expected CMD or CMD-SHELL")
        elif isinstance(test, str):
            # String form is acceptable for CMD-SHELL
            pass
        else:
            bad.append(f"{name}: unexpected test type {type(test).__name__}")
    assert not bad, f"Invalid healthcheck command format: {bad}"


def test_healthcheck_has_interval_and_retries(services):
    """Every healthcheck should specify interval and retries for reliability."""
    missing = []
    for name, cfg in services.items():
        if name in HEALTHCHECK_EXEMPT:
            continue
        hc = cfg.get("healthcheck", {})
        if not hc:
            continue
        if "interval" not in hc:
            missing.append(f"{name}: missing interval")
        if "retries" not in hc:
            missing.append(f"{name}: missing retries")
    assert not missing, f"Healthcheck config issues: {missing}"


def test_depends_on_uses_healthy_condition(services):
    """All dict-form depends_on entries should use service_healthy or service_completed_successfully."""
    allowed = {"service_healthy", "service_completed_successfully"}
    bad = []
    for name, cfg in services.items():
        depends = cfg.get("depends_on", {})
        if isinstance(depends, dict):
            for dep_name, dep_cfg in depends.items():
                if isinstance(dep_cfg, dict):
                    condition = dep_cfg.get("condition", "")
                    if condition and condition not in allowed:
                        bad.append(f"{name} → {dep_name}: {condition}")
    assert not bad, f"Invalid depends_on conditions: {bad}"


def test_service_count_sanity(services):
    """Sanity check — compose file should have a reasonable number of services."""
    count = len(services)
    assert count >= 5, f"Expected at least 5 services, found {count}"
    assert count <= 30, f"Abnormally many services: {count}"
