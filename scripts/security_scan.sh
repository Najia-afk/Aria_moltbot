#!/bin/bash
set -e
echo "=== Dependency Vulnerability Scan ==="
pip-audit --strict 2>&1 || echo "WARN: Vulnerabilities found"
echo ""
echo "=== SAST Scan (bandit) ==="
bandit -r aria_skills/ aria_engine/ src/ -c pyproject.toml -ll 2>&1 || echo "WARN: Issues found"
echo ""
echo "Done. Review findings above."
