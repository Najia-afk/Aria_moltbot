"""Verify pyproject.toml is correct for Python 3.13+ and has no OpenClaw references."""
import sys
import tomllib
from pathlib import Path


def main() -> int:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    project = config["project"]
    errors: list[str] = []

    # 1. Check requires-python
    req_python = project.get("requires-python", "")
    if "3.13" not in req_python:
        errors.append(f"requires-python should target >=3.13, got: {req_python}")

    # 2. Check no OpenClaw keywords
    keywords = project.get("keywords", [])
    for kw in keywords:
        if "openclaw" in kw.lower() or "clawdbot" in kw.lower():
            errors.append(f"OpenClaw keyword found: {kw}")

    # 3. Check classifiers only list 3.13+
    classifiers = project.get("classifiers", [])
    for cls in classifiers:
        if "Python :: 3.10" in cls or "Python :: 3.11" in cls or "Python :: 3.12" in cls:
            errors.append(f"Stale Python classifier: {cls}")

    # 4. Check new dependencies present
    deps = project.get("dependencies", [])
    dep_names = [d.split(">=")[0].split("[")[0].strip() for d in deps]
    required = ["apscheduler", "aiohttp", "litellm", "sqlalchemy", "prometheus-client"]
    for req in required:
        if req not in dep_names:
            errors.append(f"Missing dependency: {req}")

    # 5. Check aria_engine in wheel packages
    wheel_packages = (
        config.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    if "aria_engine" not in wheel_packages:
        errors.append("aria_engine not in wheel packages")

    # 6. Check version bumped
    version = project.get("version", "")
    if version.startswith("1."):
        errors.append(f"Version should be 2.x for v2 release, got: {version}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("OK: pyproject.toml validated for Python 3.13+")
    return 0


if __name__ == "__main__":
    sys.exit(main())
